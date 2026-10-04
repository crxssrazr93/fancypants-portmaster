//! PortMaster port: runs command buffer finishing, queue submission and presentation on a
//! second thread, so that the player thread can run the next frame's ActionScript while the
//! GL driver works through the previous frame (handheld CPUs are slow per core, but have four).
//!
//! Jobs run strictly in the order they were queued, so GPU work recorded into command encoders
//! keeps its order. Anything that touches the queue directly from the player thread
//! (`write_texture`, readbacks, `poll`) must call [`GpuWorker::drain`] first, since those
//! operations would otherwise overtake jobs that are still waiting.
//!
//! `RUFFLE_GPU_THREAD=0` runs every job inline instead.

use std::sync::mpsc::{Sender, channel};
use std::sync::{Arc, Condvar, Mutex};

type Job = Box<dyn FnOnce() + Send>;

#[derive(Default)]
struct Progress {
    queued: u64,
    done: u64,
}

pub struct GpuWorker {
    sender: Option<Mutex<Sender<Job>>>,
    progress: Arc<(Mutex<Progress>, Condvar)>,
}

impl std::fmt::Debug for GpuWorker {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("GpuWorker")
            .field("threaded", &self.sender.is_some())
            .finish()
    }
}

impl GpuWorker {
    pub fn new() -> Self {
        let progress: Arc<(Mutex<Progress>, Condvar)> = Default::default();
        let threaded = std::env::var("RUFFLE_GPU_THREAD").map_or(true, |v| v != "0");
        let sender = threaded.then(|| {
            let (sender, receiver) = channel::<Job>();
            let progress = progress.clone();
            std::thread::Builder::new()
                .name("ruffle-gpu".to_string())
                .spawn(move || {
                    while let Ok(job) = receiver.recv() {
                        if std::panic::catch_unwind(std::panic::AssertUnwindSafe(job)).is_err() {
                            // A waiting player thread would hang forever otherwise
                            std::process::abort();
                        }
                        let (lock, cvar) = &*progress;
                        lock.lock().expect("GPU worker lock").done += 1;
                        cvar.notify_all();
                    }
                })
                .expect("Could not start the GPU worker thread");
            Mutex::new(sender)
        });
        Self { sender, progress }
    }

    /// Queues a job and returns its id, to wait for with [`GpuWorker::wait`].
    pub fn run(&self, job: impl FnOnce() + Send + 'static) -> u64 {
        let (lock, _) = &*self.progress;
        let id = {
            let mut progress = lock.lock().expect("GPU worker lock");
            progress.queued += 1;
            progress.queued
        };
        match &self.sender {
            Some(sender) => sender
                .lock()
                .expect("GPU worker sender lock")
                .send(Box::new(job))
                .expect("GPU worker thread has stopped"),
            None => {
                job();
                lock.lock().expect("GPU worker lock").done += 1;
            }
        }
        id
    }

    /// Blocks until the job with the given id (and every job before it) has run.
    pub fn wait(&self, id: u64) {
        let (lock, cvar) = &*self.progress;
        let mut progress = lock.lock().expect("GPU worker lock");
        while progress.done < id {
            progress = cvar.wait(progress).expect("GPU worker lock");
        }
    }

    /// Blocks until every queued job has run and the GPU has finished all submitted work.
    ///
    /// This polls instead of letting wgpu block on a GL fence: `glClientWaitSync` fails on the
    /// Mali blob drivers used with Westonpack (it returns 0), which wgpu reports as a timeout.
    /// Once the work is known to be complete, wgpu's own waits return without calling it.
    pub fn wait_for_gpu(&self, device: &wgpu::Device) {
        let device = device.clone();
        self.run(move || wait_for_gpu_by_polling(&device));
        self.drain();
    }

    /// Blocks until every queued job has run.
    pub fn drain(&self) {
        let queued = self.progress.0.lock().expect("GPU worker lock").queued;
        self.wait(queued);
    }
}

impl Default for GpuWorker {
    fn default() -> Self {
        Self::new()
    }
}

/// See [`GpuWorker::wait_for_gpu`].
pub fn wait_for_gpu_by_polling(device: &wgpu::Device) {
    loop {
        match device.poll(wgpu::PollType::Poll) {
            Ok(wgpu::PollStatus::QueueEmpty) | Err(_) => break,
            _ => std::thread::sleep(std::time::Duration::from_micros(500)),
        }
    }
}

