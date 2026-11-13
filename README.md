# DDBOT 使用的 FFmpeg 静态库

当前发布工作流构建 10 个平台，产物为 `ffmpeg-<平台>.zip`。DDBOT 的内置 FFmpeg
使用这些库完成 MP4 转封装及 MP4/HLS 到 GIF 的转换。

## 2026-11-13 检查结论

当前工作流固定 FFmpeg `n7.1` 初版；Linux/macOS 使用 OpenSSL 3.3.2，Windows 使用
3.4.1；x264 从未固定版本的默认分支构建。最新现有发布为 `v7.1-131`。

建议首先升级至 FFmpeg **7.1.5**，与现有 7.1 API 保持接近；OpenSSL 统一至
**3.5.9 LTS**，该系列维护至 2030-04-08。官方当前还提供 FFmpeg 8.1.3 和 9.0.2，
跨主版本升级应另做源码、ABI 及全平台验证，不能直接用新库替换旧头文件。

版本依据：[FFmpeg 官方下载页](https://ffmpeg.org/download.html)、
[OpenSSL 3.5.9](https://github.com/openssl/openssl/releases/tag/openssl-3.5.9)、
[OpenSSL 维护策略](https://openssl-library.org/policies/releasestrat/)。

## 体积优化验证

当前配置只限制了解码器、编码器等部分组件，未关闭默认启用的解析器及 bitstream filters，
也未关闭环境依赖自动发现。现有 Windows `libavcodec.a` 包含 415 个对象文件，
其中还存在 HEVC、VP9 等 DDBOT 当前路径不需要的对象。DDBOT 没有调用 x264 或 AAC 编码器：
MP4 路径复制压缩数据，GIF 路径使用 H.264 解码器及 GIF 编码器。

`profiles/ddbot-minimal.sh` 为候选白名单配置，使用 `--disable-everything`、
`--disable-autodetect`、`--enable-small`，显式启用所需协议、封装格式、解析器、滤镜与
bitstream filters。保留 H.264/AAC/MP3 解码、MP4/GIF 输出及 HTTP(S) 代理能力，
不启用 x264、AAC 编码器；x86 汇编仍保留。

Windows 的 FFmpeg 构建不启用 `-fdata-sections`：本机 MinGW 验证发现它将零初始化的
FFT 表写入 `.data$`，让 `libavutil.a` 额外包含约 17 MB 的零数据，且会进入 DDBOT
最终文件。保留常规 `.bss` 存储可以避免此回退，无需关闭汇编或删减 TLS 算法。

2026-11-13 在 Windows amd64 / GCC 15.2.0 / NASM 2.16.03 上构建 FFmpeg 7.1.5 与
OpenSSL 3.5.9。DDBOT 使用同一份源码及相同 `-trimpath -ldflags="-s -w"` 参数，
两者都显式静态链接 Windows 运行库，通过临时 overlay 更换库及头文件、移除 x264 链接。
结果如下，单位为十进制 MB：

| 项目 | 现有库 | 候选精简库 |
| --- | ---: | ---: |
| FFmpeg 自身 5 个静态库 | 14.16 MB | 6.99 MB |
| 全部静态库（含 OpenSSL；旧包另含 x264） | 24.87 MB | 23.04 MB |
| DDBOT 可执行文件 | 45.53 MB | 38.46 MB |
| libavcodec 对象文件数 | 415 | 157 |

最终程序减少约 **15.5%**，已包含新版 OpenSSL 的体积成本，候选 ZIP 为 **6.77 MB**。
这是一台机器上的实测，旧发布库与新库的 C 编译器也不同，不能将比例直接推广到其他平台
或全部归因于单个配置项。上表采用保留汇编的结果；未做速度基准测试。

候选库通过 DDBOT 的两套码率 HLS 选流、HTTP 截断检测、无代理超时、GIF 动画及
原生日志过滤测试；额外使用 TS / fMP4 / AES-128 HLS 分别验证 MP4 双轨输出与 GIF 动画。
Windows 消费方须显式静态链接（例如 `-static`），以包含新 MinGW 时间函数依赖的运行库；
DDBOT 配套调整后，导入 DLL 清单与旧依赖基线一致，不需要额外分发 libwinpthread。
配套候选库的 DDBOT 全项目测试已通过；清除工具链 PATH 后，FFmpeg 独立测试程序仍通过。
本地在同一路径更换外部 `.a` 时，应强制重新构建 DDBOT，避免 Go 构建缓存复用旧链接结果。

OpenSSL **3.5.9** 已在本机完成静态构建，关闭应用程序、测试、文档、QUIC、
动态模块、engine、legacy provider 和压缩支持；保留汇编及现代 TLS 所需算法。
未通过大范围删除算法进一步压缩，避免影响 TLS 协商和证书兼容性。
上表为包含新版 OpenSSL 的最终本机对比，不代表 10 个平台均已验证。

Linux amd64 另在 WSL / Ubuntu 24.04 / GCC 13.3 / NASM 2.16.01 下完成 DDBOT 媒体回归和
成品构建：同一份源码、Go 1.26.2 及相同构建参数下，现有发布库生成 **42.27 MB**，
候选库生成 **36.67 MB**，减少约 **13.3%**。候选程序仅依赖系统 libc、libm 和动态加载器，
不需要额外安装共享 FFmpeg / OpenSSL。发布库与候选库的编译器不同，仍不能归因于单个开关。

新增 Linux ARM64 原生验收：在 Ubuntu 22.04 容器内完成配套 DDBOT 的媒体、日志回归及主程序
构建，成品为 **33.89 MB**。Linux amd64 / ARM64 的 CI 成品均只依赖 libc、libm 和系统加载器，
最高 GLIBC 符号版本为 **2.35**；ARM64 未做旧依赖下的同源码体积对比。

五个平台的远端构建、22 项链路检查和迁移链接验证已全部通过，产物的逐文件哈希也已复核。
平台、产物大小、源码提交及验收范围见 [跨平台验证记录](docs/validation-2026-11-13.md)。

## 候选构建与验收

`versions.env` 固定 FFmpeg / OpenSSL 版本和官方源码 SHA-256。
`scripts/build-native.sh` 在新目录构建两者，拒绝编译器与宿主架构不符，
隔离 `pkg-config` 依赖搜索，并在打包前检查实际链接版本及必要能力。

```sh
# 在 Linux/macOS 原生环境或 Windows MSYS2 UCRT64 shell 中运行。
# 目录必须不存在，且路径不含空格。
JOBS=4 bash scripts/build-native.sh "$PWD/candidate-build"
```

需要 C 编译器、make、NASM、Perl（含 ExtUtils::MakeMaker、IPC::Cmd、Pod::Usage）、
pkg-config、curl、tar/xz、Python 3.10+ 和用于生成测试证书的 OpenSSL 命令。
可通过 `CC`、`MAKE`、`PYTHON`、`OPENSSL`、`JOBS` 指定工具；
Windows 使用原生 MinGW GCC 与 MSYS2 Perl。Git 自带的精简 Perl 通常缺少构建模块。
`SOURCE_CACHE=/path/to/cache` 可读取事先下载的 `ffmpeg-<版本>.tar.xz` 和
`openssl-<版本>.tar.gz`，缓存与在线下载同样必须通过固定 SHA-256 校验。

构建完成生成 `ffmpeg-<平台>-candidate.zip` 和 `.sha256`；包内包含 5 个 FFmpeg 库、
2 个 OpenSSL 库、配套头文件、可迁移的 `.pc`、许可证、构建配置、编译器版本、
能力检查结果、链路测试结果及逐文件 SHA-256 清单。打包后还会迁移目录，
只使用包内 `.pc` 重新编译并运行能力工具，验证下游可独立链接。
版本和配置已固定；产物不承诺跨编译器、跨路径逐字节相同。

`tests/smoke.py` 的 **22 项离线检查已通过**：TS、fMP4、AES-128 HLS，HTTP 直连及
转发代理，TLS 1.2/1.3 直连及 CONNECT 代理，正确 CA 成功、错误 CA 必须失败。
测试创建临时证书，不访问公网；生成证书的 CLI 与被测静态 TLS 实现彼此独立。
具体范围见 [tests/README.md](tests/README.md)。

`.github/workflows/candidate.yml` 支持手动触发和候选分支推送，使用 Linux amd64 / ARM64、
Windows amd64、macOS Intel 和 Apple Silicon 原生 runner 构建并上传候选 artifact，不创建 release。
Linux ARM64 在原生 runner 上使用 Ubuntu 22.04 容器，与 amd64 保持相同用户空间基线。
两种 Linux 架构还检出固定 SHA 的配套 DDBOT 源码，使用 `ffmpeg_minimal` 标签运行媒体与
日志回归并构建完整程序；检查静态依赖及最高 GLIBC 符号版本不超过 2.35，上传成品和报告。
其他平台，尤其 Windows ARM/ARM64，仍需专门校正 OpenSSL 目标并验证；
不将候选配置直接复制到未验证的 10 平台发布矩阵。

## 发布前的衔接顺序

1. 将 DDBOT 下载静态库的 `releases/latest/download` 改为指定 release，并保持头文件与库同版。
   配套工作区已固定现有 `v7.1-131`，并加入 10 个平台 ZIP 的 SHA-256 校验。
2. 为候选库跑全平台构建及 MP4、TS/fMP4 HLS、GIF、HTTPS/代理验收，记录功能、版本、大小和哈希。
3. 发布新库后，再将 DDBOT 固定到该版本，并使用配套 `ffmpeg_minimal` 构建标签省略 `-lx264`。
   该标签不改变现有正式库的默认链接。当前工作流仍保留原构建，
   避免候选配置未经全平台验证就替换生产产物。

其他值得修整的构建点：

- ARM 的 OpenSSL 配置补齐 `no-shared`，统一全部平台的依赖版本及 `lib` 目录。
- 修复 macOS amd64 的 OpenSSL/x264 目标编译参数；`macos-latest` 不保证始终为 Intel。
- 将候选构建中已完成的依赖搜索隔离、`.pc` 路径修正、版本锁定及哈希清单推广到发布矩阵。
- 兼容旧流程期间如仍保留 x264，也需固定其来源和版本。
- 后续再评估平台原生 TLS，或 OpenSSL 的体积配置；这需要单独验证代理、证书与 TLS 行为。
