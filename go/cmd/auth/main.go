package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"
)

var secretKey = []byte("jordan-lenchitz-secret-key-2026")

type LoginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type AuthResponse struct {
	Token string `json:"token,omitempty"`
	Valid bool   `json:"valid"`
}

func main() {
	http.HandleFunc("/login", handleLogin)
	http.HandleFunc("/verify", handleVerify)
	log.Println("Modern Auth service starting on :8084")
	log.Fatal(http.ListenAndServe(":8084", nil))
}

func handleLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, strings.ToLower(err.Error()), http.StatusBadRequest)
		return
	}
	if req.Username == "jordan" && req.Password == "scholarly-range" {
		header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"HS256","typ":"JWT"}`))
		payload := base64.RawURLEncoding.EncodeToString([]byte(fmt.Sprintf(`{"sub":"%s","exp":%d}`, req.Username, time.Now().Add(time.Hour).Unix())))
		signature := sign(header + "." + payload)
		token := header + "." + payload + "." + signature
		json.NewEncoder(w).Encode(AuthResponse{Token: token, Valid: true})
		return
	}
	http.Error(w, "unauthorized", http.StatusUnauthorized)
}

func handleVerify(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		Token string `json:"token"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, strings.ToLower(err.Error()), http.StatusBadRequest)
		return
	}
	parts := strings.Split(req.Token, ".")
	if len(parts) != 3 {
		json.NewEncoder(w).Encode(AuthResponse{Valid: false})
		return
	}
	expectedSignature := sign(parts[0] + "." + parts[1])
	if parts[2] != expectedSignature {
		json.NewEncoder(w).Encode(AuthResponse{Valid: false})
		return
	}
	payloadBytes, _ := base64.RawURLEncoding.DecodeString(parts[1])
	var payload struct {
		Exp int64 `json:"exp"`
	}
	json.Unmarshal(payloadBytes, &payload)
	if time.Now().Unix() > payload.Exp {
		json.NewEncoder(w).Encode(AuthResponse{Valid: false})
		return
	}
	json.NewEncoder(w).Encode(AuthResponse{Valid: true})
}

func sign(data string) string {
	h := hmac.New(sha256.New, secretKey)
	h.Write([]byte(data))
	return base64.RawURLEncoding.EncodeToString(h.Sum(nil))
}
