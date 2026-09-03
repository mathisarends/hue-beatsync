package commands

import (
	"encoding/json"
	"net/http"
	"strings"
	"testing"
)

func TestDoctorPassesWhenEverythingIsSaved(t *testing.T) {
	server := newStubServer(t)
	server.defaults = `{"area":"Living Room","audio":{"device":"Microphone"}}`
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "doctor")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if !strings.Contains(stdout, "Everything a stream needs is in place.") {
		t.Fatalf("stdout = %s", stdout)
	}
}

// Without an area there is nothing to stream to, so this is the one gap that
// has to fail rather than fall back.
func TestDoctorFailsWithoutASavedArea(t *testing.T) {
	server := newStubServer(t)
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "doctor", "--json", "--compact")
	if exitCode != 1 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if stderr != "" {
		t.Fatalf("the report is the answer, but stderr = %q", stderr)
	}
	var report doctorReport
	if err := json.Unmarshal([]byte(stdout), &report); err != nil {
		t.Fatal(err)
	}
	if report.Status != statusFailed {
		t.Fatalf("report = %#v", report)
	}
	if !strings.Contains(stdout, "lichtorgel area select") {
		t.Fatalf("stdout = %s", stdout)
	}
}

func TestDoctorWarnsWhenNoDeviceIsSaved(t *testing.T) {
	server := newStubServer(t)
	server.defaults = `{"area":"Bedroom"}`
	stdout, _, exitCode := runTestCLI(t, server.URL, "doctor", "--json", "--compact")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stdout = %s", exitCode, stdout)
	}
	var report doctorReport
	if err := json.Unmarshal([]byte(stdout), &report); err != nil {
		t.Fatal(err)
	}
	if report.Status != statusWarn {
		t.Fatalf("report = %#v", report)
	}
}

func TestDoctorReportsAnUnreachableBridge(t *testing.T) {
	server := errorServer(t, http.StatusServiceUnavailable, "The Hue bridge is unreachable.")
	stdout, _, exitCode := runTestCLI(t, server.URL, "doctor")
	if exitCode != 1 {
		t.Fatalf("exit = %d, stdout = %s", exitCode, stdout)
	}
	if !strings.Contains(stdout, "failed") || !strings.Contains(stdout, "Not ready to stream yet.") {
		t.Fatalf("stdout = %s", stdout)
	}
}
