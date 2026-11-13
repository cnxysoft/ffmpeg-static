#!/usr/bin/env bash
# Optional regeneration only; smoke tests use the committed synthetic fixtures.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data/{ts,fmp4,encrypted}
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i 'testsrc2=size=64x64:rate=4:duration=1' \
  -f lavfi -i 'sine=frequency=440:sample_rate=44100:duration=1' \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -f mpegts data/ts/segment.ts
ffmpeg -y -hide_banner -loglevel error -i data/ts/segment.ts -map 0 -c copy -bsf:a aac_adtstoasc \
  -f hls -hls_segment_type fmp4 -hls_time 2 -hls_list_size 0 \
  -hls_segment_filename 'data/fmp4/segment%d.m4s' data/fmp4/index.m3u8
printf '#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:1.1,\nsegment.ts\n#EXT-X-ENDLIST\n' > data/ts/index.m3u8
# Deliberately public fixture key and IV. They protect no private media.
printf '0123456789abcdef' > data/encrypted/key.bin
openssl enc -aes-128-cbc -K 30313233343536373839616263646566 \
  -iv 00000000000000000000000000000000 -in data/ts/segment.ts -out data/encrypted/segment.ts
printf '#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin",IV=0x00000000000000000000000000000000\n#EXTINF:1.1,\nsegment.ts\n#EXT-X-ENDLIST\n' > data/encrypted/index.m3u8
