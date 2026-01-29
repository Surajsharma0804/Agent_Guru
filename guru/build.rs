fn main() {
    // Compile Native Core (C++)
    println!("cargo:rerun-if-changed=native/src/guru_core.cpp");
    
    // Check if source exists before trying to compile
    if std::path::Path::new("native/src/guru_core.cpp").exists() {
        cc::Build::new()
            .cpp(true) // Enable C++ mode
            .file("native/src/guru_core.cpp")
            .compile("guru_native");
    }
}
