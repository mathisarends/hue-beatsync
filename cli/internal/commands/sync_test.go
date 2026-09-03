package commands

import (
	"strings"
	"testing"
)

func TestStartSendsOnlyTheFlagsThatWereGiven(t *testing.T) {
	server := newStubServer(t)
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "start", "--mode", "sweep", "--json", "--compact")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	written := server.lastWrite(t)
	if !strings.Contains(written, `"mode":"sweep"`) {
		t.Fatalf("written = %s", written)
	}
	// A group nobody touched must stay out of the request, or it would erase
	// the stored defaults it silently carries.
	if strings.Contains(written, `"analysis"`) || strings.Contains(written, `"area"`) {
		t.Fatalf("written = %s", written)
	}
	if !strings.Contains(stdout, `"running":true`) {
		t.Fatalf("stdout = %s", stdout)
	}
}

func TestStartResolvesANumericDeviceToAnIndex(t *testing.T) {
	server := newStubServer(t)
	_, stderr, exitCode := runTestCLI(t, server.URL, "start", "--device", "3")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if written := server.lastWrite(t); !strings.Contains(written, `"device":3`) {
		t.Fatalf("written = %s", written)
	}
}

func TestStatusReadsIdle(t *testing.T) {
	server := newStubServer(t)
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "status")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if !strings.Contains(stdout, "Not streaming.") || !strings.Contains(stdout, "lichtorgel start") {
		t.Fatalf("stdout = %s", stdout)
	}
}

func TestStatusReadsRunning(t *testing.T) {
	server := newStubServer(t)
	server.status = `{"running":true,"area":"Bedroom"}`
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "status")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if !strings.Contains(stdout, `Streaming to "Bedroom"`) {
		t.Fatalf("stdout = %s", stdout)
	}
}

func TestStopReportsThatTheLightsStay(t *testing.T) {
	server := newStubServer(t)
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "stop")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if !strings.Contains(stdout, "Stopped.") {
		t.Fatalf("stdout = %s", stdout)
	}
}

func TestDefaultsSetNeedsSomethingToSave(t *testing.T) {
	server := newStubServer(t)
	_, stderr, exitCode := runTestCLI(t, server.URL, "defaults", "set")
	if exitCode != 2 || !strings.Contains(stderr, "nothing to save") {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
}

func TestDefaultsShowPrintsOnlyWhatIsSaved(t *testing.T) {
	server := newStubServer(t)
	server.defaults = `{"area":"Bedroom","visual":{"mode":"pulse"}}`
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "defaults")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if !strings.Contains(stdout, "Bedroom") || !strings.Contains(stdout, "pulse") {
		t.Fatalf("stdout = %s", stdout)
	}
	if strings.Contains(stdout, "Sensitivity") {
		t.Fatalf("unsaved settings were printed: %s", stdout)
	}
}

func TestDefaultsShowSaysWhenNothingIsSaved(t *testing.T) {
	server := newStubServer(t)
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "defaults", "show")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if !strings.Contains(stdout, "Nothing saved yet") {
		t.Fatalf("stdout = %s", stdout)
	}
}
