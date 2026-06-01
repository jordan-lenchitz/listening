package main

import (
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

func main() {
	http.HandleFunc("/store", handleStore)
	log.Println("Storage service starting on :8086")
	log.Fatal(http.ListenAndServe(":8086", nil))
}

func handleStore(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	file, _, err := r.FormFile("file")
	if err != nil {
		http.Error(w, "Missing file", http.StatusBadRequest)
		return
	}
	defer file.Close()

	filename := fmt.Sprintf("result_%d.png", time.Now().Unix())
	out, err := os.Create(filepath.Join(os.TempDir(), filename))
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer out.Close()

	io.Copy(out, file)
	fmt.Fprintf(w, "Stored as %s\n", filename)
}
