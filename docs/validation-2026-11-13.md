# 2026-11-13 原生候选验证

被测候选提交：[c388778](https://github.com/cnxysoft/ffmpeg-static/commit/c388778962ceb26ce9bf9b88d04521f993102013)。
CI：[Validate minimal candidate #43379784679](https://github.com/cnxysoft/ffmpeg-static/actions/runs/43379784679)，五个平台全部通过。
版本固定为 FFmpeg 7.1.5 / OpenSSL 3.5.9，官方源码 SHA-256 见 `versions.env`。

| 平台 | 原生 runner | 构建及验收 | 候选 ZIP 大小 |
| --- | --- | --- | ---: |
| Linux amd64 | ubuntu-22.04 | 通过 | 6,346,730 bytes |
| Linux ARM64 | ubuntu-24.04-arm / Ubuntu 22.04 容器 | 通过 | 6,864,637 bytes |
| Windows amd64 | windows-2022 / MSYS2 UCRT64 | 通过 | 6,767,792 bytes |
| macOS Intel | macos-15-intel | 通过 | 5,588,034 bytes |
| macOS Apple Silicon | macos-15 | 通过 | 6,183,157 bytes |

每个平台均执行了以下检查：

- 头文件与运行库 ABI、实际 FFmpeg / OpenSSL 版本、编解码器、滤镜、封装、协议及 TLS 初始化。
- 22 项本机链路检查：TS / fMP4 / AES-128 HLS，HTTP 直连及代理，TLS 1.2 / 1.3 直连及 CONNECT，
  正确 CA 成功、错误 CA 必须失败，并通过计数确认请求确实经过代理。
- 迁移目录后通过包内 `.pc` 重新编译并运行能力工具，验证依赖路径可以迁移。

CI 产物下载后，再次核对了每个 ZIP 的 SHA-256、每包 331 个文件（合计 1,655 个）的大小及
哈希、实际版本报告、22 项 PASS 记录和 `.pc` 路径。ZIP 校验如下：

```text
54af8c6129fe83bb3a53b517f51d8a74cd9351040483caffc588289dad6c6053  ffmpeg-linux-amd64-candidate.zip
c4c13cc305e6b006653db635d01f3b809624fe27dc91394920de7b023a83a3ba  ffmpeg-linux-arm64-candidate.zip
07159175a27134a7971338099997cfd2f1363625fd0c9828d54a923ab4b50677  ffmpeg-windows-amd64-candidate.zip
d3bf0e68caa0f68451880d0d9b6817e3df8270c86fa41ccbcd486be63695b69b  ffmpeg-darwin-amd64-candidate.zip
e26f519d8c17586460a018cacda245b0163765f5cce13494f167a25aee179661  ffmpeg-darwin-arm64-candidate.zip
```

## DDBOT 消费方验证

Linux CI 固定检出 DDBOT 配套提交
[4cd8406](https://github.com/cnxysoft/DDBOT-WSa/commit/4cd840653327aa4707ce2b71e35b5eaa2f64bd35)，
使用 Go 1.26.2、CGO 和 `ffmpeg_minimal` 标签，安装本轮候选头文件及静态库。
该标签省略 x264 链接，默认构建继续兼容现有正式库。

两种 Linux 架构均运行以下检查，然后以 `-trimpath -ldflags='-s -w'` 构建完整 DDBOT：

- TS / fMP4 / AES-128 HLS 各转 MP4 与 GIF，共 6 项；检查 MP4 音视频双轨和 GIF 动画。
- DDBOT 自身 FFmpeg 包回归：多码率选流、HTTP 截断、失败文件清理、无代理输入超时。
- 日志级别、quiet 过滤、DD 结构化字段及严重度映射、CLI stderr 分段处理。
- ELF 架构、成品 SHA-256、动态依赖及最高 GLIBC 符号要求；缺失依赖、共享 FFmpeg /
  OpenSSL / x264、超过 GLIBC 2.35 均令 CI 失败。

| 本轮 Linux CI 成品 | 文件大小 | 最高 GLIBC 符号版本 |
| --- | ---: | --- |
| DDBOT-candidate-linux-amd64 | 36,672,568 bytes | 2.35 |
| DDBOT-candidate-linux-arm64 | 33,885,920 bytes | 2.35 |

两份成品仅动态依赖 libc、libm 和系统加载器，无需额外安装共享 FFmpeg / OpenSSL。
下载后已复核成品哈希、ELF 机器类型、6 项转换及原有回归的 PASS 记录，校验如下：

```text
f8d563ce29bf095f463d329fd2a326039581a8fed4fab2ec4a1651806af5fa7a  DDBOT-candidate-linux-amd64
432f8f5a3dedc2e97b56cc8b32732c18a18ef1da453a6bbf82c408482fe5ec13  DDBOT-candidate-linux-arm64
```

ARM64 初次在 Ubuntu 24.04 用户空间构建时功能测试通过，但成品引用了 `fmod@GLIBC_2.38`。
最终改为 ARM64 原生 runner 上的 Ubuntu 22.04 容器构建及运行验收，消除此基线抬升，
并为两种 Linux 架构加入 GLIBC 2.35 上限。未验证更早的发行版或 musl 环境。

## 本机成品体积对比

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

这是此前本机同源码、同参数的成品体积对比，与上面的 Linux CI 成品分开记录；
旧依赖与候选依赖的 C 编译器也不同。ARM64 未做旧依赖基线对比；未测转换速度。
macOS 当前通过静态库能力、链路和迁移链接验收，尚未构建配套完整 DDBOT 成品。
Linux 386 / ARM、Windows 386 / ARM / ARM64 未纳入本轮矩阵，原 10 平台正式发布流程仍保持独立。

首轮四平台记录保留在
[CI #43372898673](https://github.com/cnxysoft/ffmpeg-static/actions/runs/43372898673)，
其源码为 [28ac34b](https://github.com/cnxysoft/ffmpeg-static/commit/28ac34b6e258bd6b19cdcd92a0d3e0ac412e182d)。
