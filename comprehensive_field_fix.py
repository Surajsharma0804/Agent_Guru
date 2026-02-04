#!/usr/bin/env python3
"""
Comprehensive Field Fix Script for AGENT_GURU
Addresses remaining struct field naming issues and missing field definitions
"""

import os
import re
import subprocess
from pathlib import Path

def run_cargo_check():
    """Run cargo check and return error output"""
    try:
        result = subprocess.run(
            ['cargo', 'check', '--message-format=short'],
            capture_output=True,
            text=True,
            cwd='.'
        )
        return result.stderr
    except Exception as e:
        print(f"Error running cargo check: {e}")
        return ""

def fix_struct_field_issues():
    """Fix struct field naming and missing field issues"""
    
    # Define field mappings for common struct issues
    field_fixes = {
        # Vision module fixes
        'guru/vision/mod.rs': [
            ('_max_latency_ms', 'max_latency_ms'),
            ('_max_tracked_objects', 'max_tracked_objects'),
            ('_camera_id', 'camera_id'),
        ],
        
        # Security biometric fixes
        'guru/security/biometric/face.rs': [
            ('landmark_count', '_landmark_count'),
            ('consecutive_frames', '_consecutive_frames'),
            ('tracking_frames', '_tracking_frames'),
            ('lbp_radius', '_lbp_radius'),
            ('lbp_points', '_lbp_points'),
        ],
        
        # Voice module fixes
        'guru/voice/mod.rs': [
            ('sample_rate', '_sample_rate'),
            ('buffer_size', '_buffer_size'),
            ('buffer_size_ms', '_buffer_size_ms'),
        ],
        
        # Memory encryption fixes
        'guru/memory/encryption.rs': [
            ('kdf_memory_cost', '_kdf_memory_cost'),
            ('kdf_iterations', '_kdf_iterations'),
            ('kdf_parallelism', '_kdf_parallelism'),
        ],
        
        # Platform fixes
        'guru/platform/windows.rs': [
            ('process_id', '_process_id'),
            ('window_count', '_window_count'),
        ],
        'guru/platform/macos.rs': [
            ('process_id', '_process_id'),
            ('window_count', '_window_count'),
        ],
        'guru/platform/linux.rs': [
            ('process_id', '_process_id'),
            ('window_count', '_window_count'),
        ],
    }
    
    # Apply field fixes
    for file_path, fixes in field_fixes.items():
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            for old_field, new_field in fixes:
                # Fix struct field definitions
                content = re.sub(
                    rf'\b{re.escape(old_field)}\s*:',
                    f'{new_field}:',
                    content
                )
                
                # Fix field access patterns
                content = re.sub(
                    rf'\.{re.escape(old_field)}\b',
                    f'.{new_field}',
                    content
                )
            
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Applied field fixes to {file_path}")

def add_missing_struct_fields():
    """Add missing struct fields based on compilation errors"""
    
    struct_additions = {
        # Vision BoundingBox missing fields
        'guru/vision/mod.rs': {
            'struct BoundingBox': [
                'width: f32,',
                'height: f32,',
                'class_id: u32,',
            ]
        },
        
        # Vision ImageData missing fields  
        'guru/vision/mod.rs': {
            'struct ImageData': [
                'width: u32,',
                'height: u32,',
                'channels: u8,',
                'camera_id: u32,',
            ]
        },
        
        # Audio processor missing fields
        'guru/security/biometric/voice.rs': {
            'struct AudioProcessor': [
                '_sampling_rate: u32,',
                '_frame_length: usize,',
                '_frame_step: usize,',
            ]
        },
        
        # Face recognition missing fields
        'guru/security/biometric/face.rs': {
            'struct LandmarkModel': [
                '_landmark_count: usize,',
            ],
            'struct BlinkDetector': [
                '_consecutive_frames: u32,',
            ],
            'struct HeadMovementDetector': [
                '_tracking_frames: u32,',
            ],
            'struct TextureAnalyzer': [
                '_lbp_radius: u8,',
                '_lbp_points: u8,',
            ]
        },
    }
    
    for file_path, struct_defs in struct_additions.items():
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            for struct_name, fields in struct_defs.items():
                # Find struct definition and add missing fields
                struct_pattern = rf'(pub\s+)?struct\s+{re.escape(struct_name.replace("struct ", ""))}\s*\{{'
                match = re.search(struct_pattern, content)
                
                if match:
                    # Find the closing brace of the struct
                    start_pos = match.end()
                    brace_count = 1
                    pos = start_pos
                    
                    while pos < len(content) and brace_count > 0:
                        if content[pos] == '{':
                            brace_count += 1
                        elif content[pos] == '}':
                            brace_count -= 1
                        pos += 1
                    
                    if brace_count == 0:
                        # Insert fields before the closing brace
                        insert_pos = pos - 1
                        fields_text = '\n    ' + '\n    '.join(fields) + '\n'
                        
                        # Check if fields already exist
                        struct_content = content[start_pos:insert_pos]
                        fields_to_add = []
                        
                        for field in fields:
                            field_name = field.split(':')[0].strip()
                            if field_name not in struct_content:
                                fields_to_add.append(field)
                        
                        if fields_to_add:
                            fields_text = '\n    ' + '\n    '.join(fields_to_add)
                            content = content[:insert_pos] + fields_text + content[insert_pos:]
            
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Added missing fields to {file_path}")

def fix_variable_scope_issues():
    """Fix remaining variable scope issues"""
    
    scope_fixes = [
        # Policy engine property tests
        ('guru/policy/engine/property_tests.rs', [
            ('decision1', '_decision1'),
            ('engine', '_engine'),
            ('metrics', '_metrics'),
        ]),
        
        # Platform modules
        ('guru/platform/windows.rs', [
            ('code', '_code'),
            ('process_id', '_process_id'),
            ('app_name', '_app_name'),
        ]),
        
        # Avatar modules
        ('guru/avatar/emotion_controller.rs', [
            ('base_rules', '_base_rules'),
            ('modified_prob', '_modified_prob'),
        ]),
    ]
    
    for file_path, var_fixes in scope_fixes:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            for old_var, new_var in var_fixes:
                # Fix variable declarations
                content = re.sub(
                    rf'\blet\s+{re.escape(old_var)}\s*=',
                    f'let {new_var} =',
                    content
                )
                
                # Fix variable usage
                content = re.sub(
                    rf'\b{re.escape(old_var)}\b(?!\s*=)',
                    new_var,
                    content
                )
            
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Fixed variable scope issues in {file_path}")

def main():
    """Main execution function"""
    print("Starting comprehensive field fix...")
    
    print("1. Fixing struct field issues...")
    fix_struct_field_issues()
    
    print("2. Adding missing struct fields...")
    add_missing_struct_fields()
    
    print("3. Fixing variable scope issues...")
    fix_variable_scope_issues()
    
    print("4. Running compilation check...")
    errors = run_cargo_check()
    
    if errors:
        error_count = len([line for line in errors.split('\n') if 'error[E' in line])
        print(f"Remaining compilation errors: {error_count}")
        
        # Show first 20 errors for analysis
        error_lines = [line for line in errors.split('\n') if 'error[E' in line][:20]
        for error in error_lines:
            print(f"  {error}")
    else:
        print("✅ No compilation errors found!")
    
    print("Comprehensive field fix completed.")

if __name__ == "__main__":
    main()