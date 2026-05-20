#include <iostream>
#include <vector>
#include <string>
#include <cstring>
// Include the YottaDB C API header. 
// (Requires YottaDB to be installed and headers in your include path)
#include <libyottadb.h>

/**
 * Helper function to push a detected pitch directly into a MUMPS Global using YottaDB C API.
 * Maps to: ^F0TRACK("FRAME", frame_id, pitch_idx) = freq^salience
 */
void push_pitch_to_yottadb(int frame_id, int pitch_idx, double freq, double salience) {
    ydb_buffer_t varname;
    varname.buf_addr = (char*)"^F0TRACK";
    varname.len_used = strlen(varname.buf_addr);
    varname.len_alloc = varname.len_used;

    ydb_buffer_t subs[3];
    
    // Subscript 1: "FRAME"
    subs[0].buf_addr = (char*)"FRAME";
    subs[0].len_used = 5;
    subs[0].len_alloc = 5;
    
    // Subscript 2: frame_id
    std::string frm_str = std::to_string(frame_id);
    subs[1].buf_addr = (char*)frm_str.c_str();
    subs[1].len_used = frm_str.length();
    subs[1].len_alloc = frm_str.length();
    
    // Subscript 3: pitch_idx
    std::string p_str = std::to_string(pitch_idx);
    subs[2].buf_addr = (char*)p_str.c_str();
    subs[2].len_used = p_str.length();
    subs[2].len_alloc = p_str.length();
    
    // Value: freq^salience
    std::string val_str = std::to_string(freq) + "^" + std::to_string(salience);
    ydb_buffer_t val;
    val.buf_addr = (char*)val_str.c_str();
    val.len_used = val_str.length();
    val.len_alloc = val_str.length();
    
    // Call the YottaDB Simple API to set the node
    int status = ydb_set_s(&varname, 3, subs, &val);
    if (status != YDB_OK) {
        std::cerr << "YottaDB Error: Failed to write frame " << frame_id << "\n";
    }
}

int main() {
    std::cout << "Starting C++ DSP Engine (YottaDB Binding)\n";
    std::cout << "Connecting to YottaDB instance...\n";
    
    // Initialize YottaDB (implicitly handled by the first API call, but we can verify)
    
    // Simulate audio processing frames
    for (int frame = 0; frame < 5; ++frame) {
        std::cout << "Processing FFT for Frame " << frame << "...\n";
        
        // Simulate extracting fundamental frequencies
        double f0 = 440.0 + (frame * 2.5); // Drifting pitch A4
        double f0_salience = 0.95;
        
        double f1 = 554.37 + (frame * 1.5); // Drifting pitch C#5
        double f1_salience = 0.88;
        
        // Push pitches directly into the MUMPS hierarchical global
        push_pitch_to_yottadb(frame, 1, f0, f0_salience);
        push_pitch_to_yottadb(frame, 2, f1, f1_salience);
    }
    
    std::cout << "DSP Processing complete. Pitches successfully written to YottaDB globals.\n";
    std::cout << "Run the MUMPS routine DO PROCESS^F0TRACK to track the voices!\n";
    return 0;
}
