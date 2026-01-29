
pub mod security;
pub mod core;
pub mod voice;
pub mod vision;
pub mod intelligence;
pub mod memory;
pub mod agents;
pub mod llm;
pub mod policy;
pub mod platform;
pub mod observability;
pub mod formal;
pub mod build;
pub mod tools;
pub mod tests;

#[derive(Debug, PartialEq)]
pub enum ModuleStatus {
    Initialized,
    Running,
    Stopped,
    Error,
}

pub type GuruResult<T> = Result<T, String>;

pub trait GuruModule {
    fn init(&self) -> GuruResult<()>;
    fn status(&self) -> ModuleStatus;
    fn shutdown(&self) -> GuruResult<()>;
}
