# 2026-11-13 精简库正式验收

版本：FFmpeg 7.1.5 / OpenSSL 3.5.9。
被测提交：[57cbca9](https://github.com/cnxysoft/ffmpeg-static/commit/57cbca97514de7e083eb3eba7fdb58aee4409edc)。
九平台 CI：[#43392112464](https://github.com/cnxysoft/ffmpeg-static/actions/runs/43392112464)，全部通过。
DDBOT 固定消费方为 [c1c1914](https://github.com/cnxysoft/DDBOT-WSa/commit/c1c191435740e1cc9f86314fe890db760476acad)，
使用 Go 1.26.2、CGO 和实际默认构建，不使用 `ffmpeg_minimal` 标签。

发布 [v7.1.5-1](https://github.com/cnxysoft/ffmpeg-static/releases/tag/v7.1.5-1)
直接晋升本轮通过验收的 ZIP，不重新构建。DDBOT 默认切换到该版本，固定九包 SHA-256。

## 本轮范围与产物

| 目标 | 库 ZIP bytes | DDBOT bytes | 最高 GLIBC 符号 / 依赖 |
| --- | ---: | ---: | --- |
| darwin-amd64 | 5,589,036 | 36,967,336 | 系统库 |
| darwin-arm64 | 6,183,917 | 34,079,138 | 系统库 |
| linux-386 | 6,375,704 | 33,969,552 | 2.35 |
| linux-amd64 | 6,347,397 | 36,672,536 | 2.35 |
| linux-arm | 5,565,251 | 30,574,376 | 2.35 |
| linux-arm64 | 6,865,321 | 33,857,248 | 2.35 |
| windows-386 | 5,733,688 | 34,066,432 | 系统库 |
| windows-amd64 | 6,768,479 | 37,493,760 | 系统库 |
| windows-arm64 | 6,311,215 | 32,866,816 | 系统库 |

全部目标执行 ABI/实际版本/能力检查、22 项本地 HLS/HTTPS/代理检查和迁移 `.pc` 链接验证，
以及 DDBOT 媒体包回归、六项 TS/fMP4/AES-128 HLS 到 MP4/GIF 转换、完整根模块测试、
vet 和主程序构建。MP4 检查音视频双轨，GIF 解码后检查动画帧。
日志回归覆盖过滤阈值、quiet、DD 字段和严重度映射、CLI stderr 分段及截断；
媒体回归覆盖 HLS 选流、HTTP 截断、失败清理及输入超时。

下载后独立复核全部九个 ZIP、合计 2,997 个清单文件的大小及 SHA-256、版本、位数、
22 项 PASS、`.pc` 路径，以及九份 DDBOT 的哈希、ELF/PE/Mach-O 架构和测试/依赖报告。
Windows 拒绝额外 FFmpeg/OpenSSL/MinGW 运行时 DLL；macOS 仅允许系统库；
Linux 检查实际解析的依赖和 GLIBC 2.35 上限。

```text
edf453b894d7de5889e3513bfe73254ea5d5928ef4ed79f4b666fc21a2e40c3d  ffmpeg-darwin-amd64.zip
c92e63506ae0dec272d73d3e60776de78500224524111658a9b149effbd553f2  ffmpeg-darwin-arm64.zip
66914ba2ce50da6a834becb7664de86bcdf13c091ace290352128d972ea351d4  ffmpeg-linux-386.zip
6dd75f4f06506a51cd8f074d18de0f651753c20e6e2ea1ca6b1b4969cbf359e0  ffmpeg-linux-amd64.zip
7128aba4c7c9b8debb245ffc87eff79c158393dfeb3247ab61fcb8133ddee89f  ffmpeg-linux-arm.zip
bf1b3389a77581da4065a77e383534bde4afec802d73b43dfde5dd7f79ee1e7c  ffmpeg-linux-arm64.zip
e6af602df3a712779c3f2d77e9bc2cde4132350c4305d9b2e64eaa35bf1da1de  ffmpeg-windows-386.zip
b4ab4de268979b1a06096f35987546f98e9194ac5d2d3f1b4585712a7bb35717  ffmpeg-windows-amd64.zip
a5c382ce0f762146ac11f6c13ccf887a51105eaae6c7d8ba63f96f8036276b1b  ffmpeg-windows-arm64.zip
```

## 平台校正与验收边界

- Linux amd64/ARM64 使用 Ubuntu 22.04 用户空间；ARM64 在原生 runner 上运行该容器。
  初次 Ubuntu 24.04 原生构建曾引用 `fmod@GLIBC_2.38`，现已消除并加入符号上限检查。
- Linux ARMv7 hard-float 使用固定 SHA-256 的 Ubuntu QEMU 8.2.2 静态程序；目标 libc 仍为 2.35。
  同一 ARM 数据库测试二进制在 QEMU 6.2 多线程模式崩溃、单线程通过，在 QEMU 8.2 连续三轮
  并发测试通过。最终九平台 CI 保留完整并发设置及默认异步抢占，没有跳过失败测试。
  依赖审计使用目标程序正常加载时的 `LD_TRACE_LOADED_OBJECTS`，避免直接进入加载器的兼容问题。
- Linux/Windows 386 使用系统兼容执行；32 位测试的大整数期望值显式转换为 `int64`。
- macOS Intel/Apple Silicon 和 Windows amd64/ARM64 使用对应原生 runner。
  macOS 部署目标为 13.0；Windows ARM64 OpenSSL 使用 C 后端，FFmpeg 汇编保留。
- 当前 Go 不支持 Windows ARM32，已从正式矩阵移除。
- 更新检查与图片处理单测改用本地 HTTP 响应/生成 JPEG，避免 GitHub 限流和外网超时污染结果。
- 修正通知测试中等待消费者退出后才关闭输入的死锁；本机与 ARM QEMU 各连续 50 次通过。
- 未进行速度基准、musl 或更早发行版验收；上述动态链接基线不替代具体系统运行测试。

## 本机体积对比

旧库来自 `v7.1-131`，比较时使用同份 DDBOT 源码与相同
`-trimpath -ldflags='-s -w'`；Windows 均显式静态链接运行库。

| 平台 | 旧依赖 DDBOT | 精简依赖 DDBOT | 减少 |
| --- | ---: | ---: | ---: |
| Windows amd64 | 45,532,160 bytes | 38,458,880 bytes | 15.5% |
| Linux amd64 | 42,268,456 bytes | 36,665,720 bytes | 13.3% |

这与上面的最终 CI 成品分开记录，旧库与新库的 C 编译器也不同，不能归因于单个配置项，
也不能将比例推广到其他平台。新版 OpenSSL 的体积成本已计入。ARM64 未做旧依赖基线对比。

早期五平台记录为 [CI #43379784679](https://github.com/cnxysoft/ffmpeg-static/actions/runs/43379784679)，
被测提交为 [c388778](https://github.com/cnxysoft/ffmpeg-static/commit/c388778962ceb26ce9bf9b88d04521f993102013)。
当时完整消费方仅验证 Linux amd64/ARM64；最终发布采用本页九目标完整验收结果。

## DDBOT 默认实现切换与发布验收

DDBOT `next-dev` 的最终集成为
[034bed2](https://github.com/cnxysoft/DDBOT-WSa/commit/034bed23bb02f86dc9a86ffe966fdc3c74753ac4)。
正式 [CI #43400570734](https://github.com/cnxysoft/DDBOT-WSa/actions/runs/43400570734)
已通过根模块全量测试、vet、适配器测试与 vet，以及九个平台的 CLI / CGO 构建，共 18 个成品。
[预览发布 #43401258013](https://github.com/cnxysoft/DDBOT-WSa/actions/runs/43401258013)
成功晋升这次 CI 的成品到 [preview-next-dev](https://github.com/cnxysoft/DDBOT-WSa/releases/tag/preview-next-dev)。

默认 CGO 构建直接使用本次精简库并移除 x264 链接，CLI 构建显式禁用 CGO。
两种后端的原生日志统一进入 DD 格式，`ffmpeg.logLevel` 默认为 warning，支持热更新及全局日志过滤。

消费方正式发布链另外校正了两项构建环境要求：

- Windows 386 库来自 MINGW32/MSVCRT，交叉编译使用固定版本和 SHA-256 的 LLVM-mingw MSVCRT；
  amd64/ARM64 使用对应 UCRT 发行包。本地执行该工具链交叉编译出的 386 媒体测试，
  六项 HLS 转换、选流、失败清理、超时及日志回归全部通过；限制 PATH 到系统目录后仍可运行，
  完整应用仅导入 Windows 系统 DLL。
- Linux 发布构建固定 Ubuntu 22.04；CLI 和 amd64/ARM/ARM64 CGO 成品检查为静态可执行文件。
  386 CGO 保留系统 libc 动态链接，实际最高 GLIBC 符号为 2.35。上传前增加依赖检查，
  拒绝共享 FFmpeg/OpenSSL 和超过该基线的成品。此前 `ubuntu-latest` 曾将 386 需求抬高到 2.43，
  已通过固定环境消除。

验收期间也将虎牙订阅、AcFun 频道/直播页/订阅测试改为固定 HTTP 响应，保留流程和字段校验，
避免公网房间变动、限流及超时影响正式全量测试；生产模块行为不变。
