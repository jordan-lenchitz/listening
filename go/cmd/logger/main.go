package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"
)

type LogMessage struct {
	Level   string `json:"level"`
	Service string `json:"service"`
	Message string `json:"message"`
}

func main() {
	http.HandleFunc("/log", handleLog)
	log.Println("Logger service starting on :8085")
	log.Fatal(http.ListenAndServe(":8085", nil))
}

func handleLog(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var msg LogMessage
	if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
		http.Error(w, strings.ToLower(err.Error()), http.StatusBadRequest)
		return
	}
	fmt.Printf("[%s] %s | %s: %s\n", time.Now().Format(time.RFC3339), msg.Level, msg.Service, msg.Message)
	w.WriteHeader(http.StatusOK)
}
