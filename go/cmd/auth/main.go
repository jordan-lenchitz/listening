package main

import (
	"encoding/json"
	"log"
	"net/http"
)

type AuthRequest struct {
	Token string `json:"token"`
}

type AuthResponse struct {
	Valid bool `json:"valid"`
}

func main() {
	http.HandleFunc("/verify", handleVerify)
	log.Println("Auth service starting on :8084")
	log.Fatal(http.ListenAndServe(":8084", nil))
}

func handleVerify(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req AuthRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	resp := AuthResponse{Valid: req.Token == "super-secret-token"}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}
