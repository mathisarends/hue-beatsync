package commands

import (
	"strings"
	"testing"
)

func TestAreaListShowsEveryArea(t *testing.T) {
	server := newStubServer(t)
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "area")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if !strings.Contains(stdout, "Living Room") || !strings.Contains(stdout, "area-2") {
		t.Fatalf("stdout = %s", stdout)
	}
}

func TestDeviceListMarksTheDefault(t *testing.T) {
	server := newStubServer(t)
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "device", "list")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if !strings.Contains(stdout, "1 *") || !strings.Contains(stdout, "Microphone") {
		t.Fatalf("stdout = %s", stdout)
	}
}

func TestAreaSelectPersistsTheName(t *testing.T) {
	server := newStubServer(t)
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "area", "select", "living")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if written := server.lastWrite(t); !strings.Contains(written, `"area":"Living Room"`) {
		t.Fatalf("written = %s", written)
	}
	if !strings.Contains(stdout, `Saved "Living Room"`) {
		t.Fatalf("stdout = %s", stdout)
	}
}

func TestAreaSelectRejectsAnUnknownArea(t *testing.T) {
	server := newStubServer(t)
	_, stderr, exitCode := runTestCLI(t, server.URL, "area", "select", "Kitchen")
	if exitCode != 2 || !strings.Contains(stderr, "no entertainment area matches") {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if !strings.Contains(stderr, "Living Room, Bedroom") {
		t.Fatalf("stderr = %s", stderr)
	}
}

// The name is what survives a replugged headset; the index does not.
func TestDeviceSelectPersistsTheNameByDefault(t *testing.T) {
	server := newStubServer(t)
	_, stderr, exitCode := runTestCLI(t, server.URL, "device", "select", "1")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if written := server.lastWrite(t); !strings.Contains(written, `"device":"Speakers (Loopback)"`) {
		t.Fatalf("written = %s", written)
	}
}

func TestDeviceSelectByIndexPersistsTheIndex(t *testing.T) {
	server := newStubServer(t)
	_, stderr, exitCode := runTestCLI(t, server.URL, "device", "select", "Microphone", "--by-index")
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
	if written := server.lastWrite(t); !strings.Contains(written, `"device":2`) {
		t.Fatalf("written = %s", written)
	}
}

func TestSelectWithoutAnArgumentNeedsATerminal(t *testing.T) {
	server := newStubServer(t)
	_, stderr, exitCode := runTestCLI(t, server.URL, "area", "select", "--json")
	if exitCode != 2 || !strings.Contains(stderr, "an area is required") {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
}
