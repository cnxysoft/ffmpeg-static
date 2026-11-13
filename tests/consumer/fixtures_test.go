//go:build cgo

// Injected into the pinned DDBOT checkout by candidate CI.
package ffmpeg

import (
	"bytes"
	"image/gif"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestCandidateHLSConversions(t *testing.T) {
	root := os.Getenv("DDBOT_FFMPEG_FIXTURES")
	if root == "" {
		t.Fatal("DDBOT_FFMPEG_FIXTURES must point to the candidate's synthetic fixtures")
	}
	server := httptest.NewServer(http.FileServer(http.Dir(root)))
	defer server.Close()
	for _, fixture := range []string{"ts", "fmp4", "encrypted"} {
		for _, format := range []string{"mp4", "gif"} {
			t.Run(fixture+"/"+format, func(t *testing.T) {
				output := filepath.Join(t.TempDir(), "converted."+format)
				if err := ConvMediaWithProxy(server.URL+"/"+fixture+"/index.m3u8", output, "", format); err != nil {
					t.Fatal(err)
				}
				data, err := os.ReadFile(output)
				if err != nil {
					t.Fatal(err)
				}
				if format == "mp4" {
					if tracks := bytes.Count(data, []byte("trak")); tracks != 2 {
						t.Fatalf("want one video and one audio track, got %d tracks", tracks)
					}
					for _, box := range []string{"ftyp", "moov", "mdat", "avc1", "mp4a"} {
						if !bytes.Contains(data, []byte(box)) {
							t.Errorf("missing MP4 box or sample entry %s", box)
						}
					}
				} else {
					animation, err := gif.DecodeAll(bytes.NewReader(data))
					if err != nil {
						t.Fatal(err)
					}
					if len(animation.Image) < 2 {
						t.Fatal("GIF lost its animation")
					}
				}
			})
		}
	}
}
