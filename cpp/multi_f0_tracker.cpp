#include <iostream>
#include <vector>
#include <cmath>

enum class VoiceState {
    ACTIVE,
    TENTATIVE,
    INACTIVE,
    TERMINATED
};

struct VoiceTrack {
    int id;
    int start_frame;
    std::vector<double> pitches;
    std::vector<double> confidences;
    std::vector<int> frames;
    VoiceState state;

    VoiceTrack(int id, int start_frame) 
        : id(id), start_frame(start_frame), state(VoiceState::TENTATIVE) {}

    void add_observation(int frame, double pitch, double confidence) {
        frames.push_back(frame);
        pitches.push_back(pitch);
        confidences.push_back(confidence);
    }
};

int main() {
    std::cout << "A Cappella Multi-F0 Tracker (C++ Edition)\n";
    std::cout << "Initializing tracker data structures...\n";

    VoiceTrack track(1, 0);
    track.add_observation(0, 440.0, 0.95);
    track.add_observation(1, 442.0, 0.96);
    track.state = VoiceState::ACTIVE;

    std::cout << "Simulated Track ID: " << track.id 
              << ", Pitches recorded: " << track.pitches.size() << "\n";

    return 0;
}

