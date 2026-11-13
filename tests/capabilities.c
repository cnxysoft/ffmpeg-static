#include <stdio.h>
#include <string.h>

#include <libavcodec/avcodec.h>
#include <libavcodec/bsf.h>
#include <libavfilter/avfilter.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
#include <libavutil/time.h>
#include <libswscale/swscale.h>
#include <openssl/crypto.h>
#include <openssl/ssl.h>

static int failures;

static int deadline_exceeded(void *opaque) {
    return av_gettime_relative() >= *(int64_t *)opaque;
}

static void require_feature(int available, const char *kind, const char *name) {
    if (!available) {
        fprintf(stderr, "missing %s: %s\n", kind, name);
        failures++;
    }
}

static int has_protocol(const char *wanted) {
    void *opaque = NULL;
    const char *name;
    while ((name = avio_enum_protocols(&opaque, 0)))
        if (!strcmp(name, wanted))
            return 1;
    return 0;
}

static int open_media(const char *url, const char *proxy, const char *ca) {
    AVFormatContext *input = avformat_alloc_context();
    AVDictionary *options = NULL;
    AVPacket *packet = av_packet_alloc();
    int64_t deadline = av_gettime_relative() + 15000000;
    char error[AV_ERROR_MAX_STRING_SIZE];
    int result;
    if (!input || !packet) {
        avformat_free_context(input);
        av_packet_free(&packet);
        return 1;
    }
    input->interrupt_callback.callback = deadline_exceeded;
    input->interrupt_callback.opaque = &deadline;
    av_dict_set(&options, "rw_timeout", "5000000", 0);
    if (proxy && proxy[0])
        av_dict_set(&options, "http_proxy", proxy, 0);
    if (ca && ca[0]) {
        av_dict_set(&options, "tls_verify", "1", 0);
        av_dict_set(&options, "ca_file", ca, 0);
    }
    result = avformat_open_input(&input, url, NULL, &options);
    av_dict_free(&options);
    if (result >= 0)
        result = avformat_find_stream_info(input, NULL);
    if (result >= 0) {
        int packets = 0;
        while ((result = av_read_frame(input, packet)) >= 0) {
            packets++;
            av_packet_unref(packet);
        }
        if (result == AVERROR_EOF && packets > 0) {
            printf("media streams=%u packets=%d\n", input->nb_streams, packets);
            result = 0;
        } else if (result == AVERROR_EOF) {
            result = AVERROR_INVALIDDATA;
        }
    }
    if (result < 0) {
        av_strerror(result, error, sizeof(error));
        fprintf(stderr, "media open/read failed: %s\n", error);
    }
    av_packet_free(&packet);
    avformat_close_input(&input);
    return result < 0;
}

int main(int argc, char **argv) {
    const char *filters[] = {"buffer", "buffersink", "palettegen", "paletteuse", "fps", "split", "format", "scale", NULL};
    const char *demuxers[] = {"mov", "hls", "mpegts", "aac", "mp3", NULL};
    const char *protocols[] = {"http", "https", "tls", "tcp", "file", "httpproxy", "crypto", NULL};
    const char *bsfs[] = {"aac_adtstoasc", "extract_extradata", NULL};
    const enum AVCodecID decoders[] = {AV_CODEC_ID_H264, AV_CODEC_ID_AAC, AV_CODEC_ID_MP3};
    SSL_CTX *tls;

    av_log_set_level(AV_LOG_ERROR);
    require_feature((avcodec_version() >> 16) == LIBAVCODEC_VERSION_MAJOR, "ABI", "avcodec");
    require_feature((avformat_version() >> 16) == LIBAVFORMAT_VERSION_MAJOR, "ABI", "avformat");
    require_feature((avfilter_version() >> 16) == LIBAVFILTER_VERSION_MAJOR, "ABI", "avfilter");
    require_feature((avutil_version() >> 16) == LIBAVUTIL_VERSION_MAJOR, "ABI", "avutil");
    require_feature((swscale_version() >> 16) == LIBSWSCALE_VERSION_MAJOR, "ABI", "swscale");
    require_feature(OPENSSL_version_major() == OPENSSL_VERSION_MAJOR, "ABI", "OpenSSL");
    avformat_network_init();
    for (unsigned i = 0; i < sizeof(decoders) / sizeof(decoders[0]); i++)
        require_feature(avcodec_find_decoder(decoders[i]) != NULL, "decoder", avcodec_get_name(decoders[i]));
    require_feature(avcodec_find_encoder(AV_CODEC_ID_GIF) != NULL, "encoder", "gif");
    require_feature(avcodec_find_encoder_by_name("libx264") == NULL, "profile exclusion", "libx264");
    require_feature(avcodec_find_encoder(AV_CODEC_ID_AAC) == NULL, "profile exclusion", "AAC encoder");
    for (int i = 0; filters[i]; i++)
        require_feature(avfilter_get_by_name(filters[i]) != NULL, "filter", filters[i]);
    for (int i = 0; demuxers[i]; i++)
        require_feature(av_find_input_format(demuxers[i]) != NULL, "demuxer", demuxers[i]);
    for (int i = 0; protocols[i]; i++)
        require_feature(has_protocol(protocols[i]), "protocol", protocols[i]);
    for (int i = 0; bsfs[i]; i++)
        require_feature(av_bsf_get_by_name(bsfs[i]) != NULL, "bitstream filter", bsfs[i]);
    require_feature(av_guess_format("mp4", NULL, NULL) != NULL, "muxer", "mp4");
    require_feature(av_guess_format("gif", NULL, NULL) != NULL, "muxer", "gif");
    tls = SSL_CTX_new(TLS_client_method());
    require_feature(tls != NULL, "TLS", "client context");
    SSL_CTX_free(tls);
    printf("FFmpeg %s; %s; pointer-bits=%u; capability-failures=%d\n",
           av_version_info(), OpenSSL_version(OPENSSL_VERSION), (unsigned)(8 * sizeof(void *)), failures);
    if (failures)
        return 1;
    if (argc > 1)
        return open_media(argv[1], argc > 2 ? argv[2] : NULL, argc > 3 ? argv[3] : NULL);
    return 0;
}
