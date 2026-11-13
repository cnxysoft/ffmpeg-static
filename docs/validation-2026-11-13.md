# 2026-11-13 原生候选验证

被测源码提交：[28ac34b](https://github.com/cnxysoft/ffmpeg-static/commit/28ac34b6e258bd6b19cdcd92a0d3e0ac412e182d)。
CI：[Validate minimal candidate #43372898673](https://github.com/cnxysoft/ffmpeg-static/actions/runs/43372898673)。
版本固定为 FFmpeg 7.1.5 / OpenSSL 3.5.9，官方源码 SHA-256 见 `versions.env`。

| 平台 | 原生 runner | 构建及验收 | 候选 ZIP 大小 |
| --- | --- | --- | ---: |
| Linux amd64 | ubuntu-22.04 | 通过 | 6,346,731 bytes |
| Windows amd64 | windows-2022 / MSYS2 UCRT64 | 通过 | 6,767,788 bytes |
| macOS Intel | macos-15-intel | 通过 | 5,587,930 bytes |
| macOS Apple Silicon | macos-15 | 通过 | 6,183,138 bytes |

每个平台均执行了以下检查：

- 头文件与运行库 ABI、实际 FFmpeg / OpenSSL 版本、编解码器、滤镜、封装、协议及 TLS 初始化。
- 22 项本机链路检查：TS / fMP4 / AES-128 HLS，HTTP 直连及代理，TLS 1.2 / 1.3 直连及 CONNECT，
  正确 CA 成功、错误 CA 必须失败，并通过计数确认请求确实经过代理。
- 迁移目录后通过包内 `.pc` 重新编译并运行能力工具，验证依赖路径可以迁移。

CI 产物下载后，再次核对了每个 ZIP 的 SHA-256、331 个文件的大小及哈希、实际版本报告、
22 项 PASS 记录和 `.pc` 路径。ZIP 校验如下：

```text
ebbed4021df0dcdc7eb45c56ce2a2eba1d4d599b6d304b2be21772cce09d432b  ffmpeg-linux-amd64-candidate.zip
c34132b12c73dc064fb77cce0a3725e5fc53f8c9861917feb086fdeffe9f5a1f  ffmpeg-windows-amd64-candidate.zip
6c9761f8913fb0f790b65920f07eb69735e4c51ed1ad3c26328eeed7885d9028  ffmpeg-darwin-amd64-candidate.zip
8a17182a4fcd22c258c5be29acf913fe9cda6b783cecb01689c10b37069f15c2  ffmpeg-darwin-arm64-candidate.zip
```

## DDBOT 消费方验证

Windows amd64：配套源码的全项目 Go 测试通过。静态链接后不引入新的 DLL；
清除工具链 PATH，FFmpeg 测试仍能独立通过。

Linux amd64：本机 WSL 的实际系统为 Ubuntu 24.04，使用 GCC 13.3、NASM 2.16.01、Go 1.26.2。
FFmpeg 包回归及成品构建通过，TS / fMP4 / AES-128 HLS 均验证了 MP4 视频和音频双轨，以及 GIF 动画；
超时、截断输入、码率选择及日志回归也通过。候选程序的共享依赖仅有 libc、libm 和系统加载器。

两种本机构建均使用同一份 DDBOT 源码和 `-trimpath -ldflags='-s -w'`，通过临时 overlay
切换配套头文件、静态库，并在候选中移除 x264 链接。旧库基线来自固定发布 `v7.1-131`。

| 平台 | 旧依赖 DDBOT | 候选依赖 DDBOT | 减少 |
| --- | ---: | ---: | ---: |
| Windows amd64 | 45,532,160 bytes | 38,458,880 bytes | 15.5% |
| Linux amd64 | 42,268,456 bytes | 36,665,720 bytes | 13.3% |

这是本机成品体积对比，旧依赖与候选依赖的 C 编译器也不同；未测转换速度。
macOS 当前通过静态库能力、链路和迁移链接验收，尚未构建配套完整 DDBOT 成品。
Linux ARM/ARM64、Windows 386/ARM/ARM64 未纳入本轮矩阵，原 10 平台正式发布流程仍保持独立。
