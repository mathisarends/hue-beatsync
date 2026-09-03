package commands

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
)

const (
	areasJSON = `[
		{"id":"area-1","name":"Living Room","active":false,"channels":5},
		{"id":"area-2","name":"Bedroom","active":true,"channels":3}
	]`
	devicesJSON = `[
		{"index":1,"name":"Speakers (Loopback)","samplerate":48000,"channels":2,
		 "host_api":"Windows WASAPI","is_default":true,"supports_exclusive":true},
		{"index":2,"name":"Microphone","samplerate":44100,"channels":1,
		 "host_api":"MME","is_default":false,"supports_exclusive":false}
	]`
)

// runTestCLI drives the CLI exactly as main does, against a stub server. The
// dotenv path is pointed at a directory that has none, so a developer's own
// .env cannot reach into a test run.
func runTestCLI(t *testing.T, baseURL string, args ...string) (stdout, stderr string, exitCode int) {
	t.Helper()
	return runTestCLIWithInput(t, baseURL, strings.NewReader(""), args...)
}

func runTestCLIWithInput(t *testing.T, baseURL string, stdin *strings.Reader, args ...string) (string, string, int) {
	t.Helper()
	t.Setenv("LICHTORGEL_API_URL", baseURL)
	t.Setenv("NO_COLOR", "1")
	var out, errOut bytes.Buffer
	args = append([]string{"--env-file", filepath.Join(t.TempDir(), ".env")}, args...)
	code := Run(context.Background(), args, stdin, &out, &errOut)
	return out.String(), errOut.String(), code
}

// stubServer answers the read-only routes with fixed data and records what was
// written, which is what the persisting commands have to be judged on.
type stubServer struct {
	*httptest.Server
	defaults string
	written  []string
	status   string
}

func newStubServer(t *testing.T) *stubServer {
	t.Helper()
	stub := &stubServer{defaults: `{}`, status: `{"running":false,"area":null}`}
	stub.Server = httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		writer.Header().Set("Content-Type", "application/json")
		switch {
		case request.URL.Path == "/areas":
			_, _ = writer.Write([]byte(areasJSON))
		case request.URL.Path == "/devices":
			_, _ = writer.Write([]byte(devicesJSON))
		case request.URL.Path == "/status":
			_, _ = writer.Write([]byte(stub.status))
		case request.URL.Path == "/defaults" && request.Method == http.MethodGet:
			_, _ = writer.Write([]byte(stub.defaults))
		case request.URL.Path == "/defaults" && request.Method == http.MethodPut:
			body := new(bytes.Buffer)
			_, _ = body.ReadFrom(request.Body)
			stub.written = append(stub.written, body.String())
			stub.defaults = body.String()
			_, _ = writer.Write([]byte(stub.defaults))
		case request.URL.Path == "/start":
			body := new(bytes.Buffer)
			_, _ = body.ReadFrom(request.Body)
			stub.written = append(stub.written, body.String())
			_, _ = writer.Write([]byte(`{"running":true,"area":"Living Room"}`))
		case request.URL.Path == "/stop":
			_, _ = writer.Write([]byte(`{"running":false,"area":null}`))
		default:
			t.Errorf("unexpected request %s %s", request.Method, request.URL.Path)
			writer.WriteHeader(http.StatusNotFound)
		}
	}))
	t.Cleanup(stub.Close)
	return stub
}

func (s *stubServer) lastWrite(t *testing.T) string {
	t.Helper()
	if len(s.written) == 0 {
		t.Fatal("nothing was written to the server")
	}
	return s.written[len(s.written)-1]
}

// errorServer answers everything with one status and detail, which is how the
// server reports an unreachable bridge or a stream that is already running.
func errorServer(t *testing.T, status int, detail string) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		writer.Header().Set("Content-Type", "application/json")
		writer.WriteHeader(status)
		_, _ = writer.Write([]byte(`{"detail":"` + detail + `"}`))
	}))
	t.Cleanup(server.Close)
	return server
}
