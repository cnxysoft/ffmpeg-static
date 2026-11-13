# DDBOT 使用的 FFmpeg 静态库

`v7.1.5-1` 使用 **FFmpeg 7.1.5 / OpenSSL 3.5.9 LTS**，面向 DDBOT 的 MP4 转封装及
H.264 视频到 GIF 转换。源码版本和官方 SHA-256 固定在 [versions.env](versions.env)。
配套 DDBOT 默认链接精简库；使用旧版消费方代码时，需要省略 `-lx264`。

## 支持范围

| 平台 | 构建与运行验收环境 |
| --- | --- |
| Linux amd64 | Ubuntu 22.04 原生 |
| Linux 386 | Ubuntu 22.04 交叉编译，x86 兼容执行 |
| Linux ARMv7 hard-float | Ubuntu 22.04 交叉编译，QEMU 执行 |
| Linux ARM64 | 原生 ARM64 runner，Ubuntu 22.04 容器 |
| macOS Intel / Apple Silicon | 对应架构原生 runner，最低部署目标 macOS 13.0 |
| Windows amd64 / 386 | MSYS2 UCRT64 / MINGW32，386 使用系统兼容执行 |
| Windows ARM64 | 原生 ARM64 runner，MSYS2 CLANGARM64 |

当前 Go 工具链不支持 Windows ARM32，因此不再发布该目标。
Windows ARM64 的 OpenSSL 使用 C 后端，FFmpeg 仍保留 ARM64 汇编。
Linux 消费方动态构建的 GLIBC 符号上限为 2.35；这不替代具体发行版上的运行验收。

## 精简配置与体积

[profiles/ddbot-minimal.sh](profiles/ddbot-minimal.sh) 从 `--disable-everything` 和
`--disable-autodetect` 开始，显式启用 H.264/AAC/MP3 解码、GIF 编码、MP4/GIF 输出、
TS/fMP4/AES-128 HLS、HTTPS/HTTP 代理和转换所需滤镜，不构建 x264 或 AAC 编码器。
MP4 复制压缩数据，GIF 解码 H.264 后编码。汇编保留。

OpenSSL 关闭应用程序、测试、文档、QUIC、动态模块、engine、legacy provider 和压缩，
保留现代 TLS 与证书兼容性所需算法，未通过大范围删除算法进一步压缩。

同份 DDBOT 源码、同样 `-trimpath -ldflags='-s -w'` 参数的本机体积对比如下；
Windows 两者均静态链接运行库，旧依赖来自 `v7.1-131`：

| 平台 | 旧依赖 DDBOT | 精简依赖 DDBOT | 减少 |
| --- | ---: | ---: | ---: |
| Windows amd64 | 45,532,160 bytes | 38,458,880 bytes | 15.5% |
| Linux amd64 | 42,268,456 bytes | 36,665,720 bytes | 13.3% |

旧库与新库的 C 编译器也不同，比例不能直接推广到其他平台或归因于单个开关；未测转换速度。
Windows FFmpeg 不启用 `-fdata-sections`，避免 MinGW 将零初始化 FFT 表写入 `.data$`，
导致约 17 MB 文件体积回退。Windows 消费方显式静态链接，避免额外分发编译器运行时 DLL。

## 构建与验收

```sh
# 在 Linux/macOS 或 Windows MSYS2 对应环境运行；目录必须不存在且路径不含空格。
JOBS=4 bash scripts/build-native.sh "$PWD/candidate-build"
```

需要 C 编译器、make、NASM（x86）、Perl（含 ExtUtils::MakeMaker、IPC::Cmd、Pod::Usage）、
pkg-config、curl、tar/xz、Python 3.10+ 和生成测试证书所用的 OpenSSL CLI。
支持 `CC`、`MAKE`、`PYTHON`、`OPENSSL`、`JOBS` 和 `SOURCE_CACHE`。
交叉编译用 `TARGET` 指定目标、`TARGET_RUNNER` 指定单个执行包装器；脚本检查编译器目标。
Linux ARM 详情见 [测试说明](tests/README.md)。

产物 `ffmpeg-<平台>-candidate.zip` 包含配套头文件、5 个 FFmpeg 库、2 个 OpenSSL 库、
可迁移 `.pc`、许可证、构建配置、工具链信息、验收记录和逐文件哈希。
构建隔离宿主依赖搜索，打包后将目录迁移，再仅通过包内 `.pc` 编译运行能力工具。
版本与配置固定；不承诺跨编译器、跨路径逐字节一致。

[candidate.yml](.github/workflows/candidate.yml) 在九个目标上运行：

- ABI、实际版本、编解码器/封装/滤镜/协议和 TLS 初始化检查。
- 22 项本地链路检查：TS/fMP4/AES-128 HLS，HTTP 直连/转发代理，TLS 1.2/1.3 直连/CONNECT，
  正确 CA 成功和错误 CA 拒绝，并核对实际代理请求计数。
- 固定 SHA 的 DDBOT 媒体回归、六项 HLS 到 MP4/GIF 转换、完整根模块测试、vet 和主程序构建。
- 成品架构、SHA-256、共享依赖与 Linux GLIBC 基线检查。

链路与媒体样本由仓库自行生成，测试在本机启动服务，不访问镜像站或发送 IM。
确切验收提交、运行记录与限制见 [跨平台验证记录](docs/validation-2026-11-13.md)。

## 发布与消费

[build.yml](.github/workflows/build.yml) 仅从**标签对应提交已经成功的九平台验收**中下载
候选 artifact，逐文件复核后发布原 ZIP，不重复构建。缺少平台、哈希不符、版本不符或能力
检查失败会阻止发布。发布包含每包校验、`SHA256SUMS` 和 `release-manifest.json`。

DDBOT 固定 `v7.1.5-1` 并按目标 ZIP 的 SHA-256 验证下载。升级时同时更新版本和校验清单，
始终配套替换头文件及静态库。若在原路径替换 `.a`，须强制重建或使用新构建缓存；
Go 缓存不会自动跟踪外部静态库内容。CLI 后端继续使用系统 FFmpeg。

Windows 消费方工具链须匹配库的 C 运行时：386 使用 MSVCRT，amd64/ARM64 使用 UCRT。
例如 LLVM-mingw 交叉编译 386 时应选择 `msvcrt` 发行包；统一使用 `ucrt` 会使
32 位 OpenSSL 的 `__vsnprintf` 导入无法解析。静态链接编译器运行库不能替代 C 运行时匹配。

FFmpeg 跨主版本升级、其他编解码器和替换 TLS 实现均需独立验收；本轮保留 7.1 API 系列。
