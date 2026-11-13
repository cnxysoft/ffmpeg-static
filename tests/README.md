# 候选库检查

`capabilities.c` 使用候选头文件和静态库编译，检查 5 个 FFmpeg 库的 ABI 主版本、
OpenSSL ABI、所需编解码器/滤镜/封装/协议，以及 TLS 客户端初始化。
`scripts/build-native.sh` 另外要求实际链接版本与 `versions.env` 一致。
工具也可接受 `URL [HTTP代理] [CA文件]`，读取媒体至 EOF，并要求存在数据包；
网络读写限时 5 秒，完整读取限时 15 秒。

`smoke.py /path/to/capabilities` 使用标准库在本机启动 HTTP、HTTPS、HTTP 代理，
运行 22 项检查：TS / fMP4 / AES-128 HLS，直连 / HTTP 转发 / HTTPS CONNECT，
TLS 1.2 / 1.3，以及错误 CA 必须失败。通过计数确认请求实际经过代理。
测试清除进程的代理环境变量，使用临时自签名证书，无需访问公网或发送 IM。

测试需要 Python 3.10+、支持 TLS 1.3 的 Python `ssl`，以及支持 `req -addext` 的
`openssl` 命令。可用 `OPENSSL=/path/to/openssl` 指定证书生成工具；它只负责生成
证书，被测 TLS 实现始终是能力工具静态链接的候选 OpenSSL。

`data/` 是一秒的自生成 H.264/AAC 视频和正弦波音频，包含 MPEG-TS、fMP4 和
AES-128 加密变体，不包含第三方素材。密钥 `0123456789abcdef`、全零 IV 仅供测试。
如需重新生成，安装完整 FFmpeg CLI 与 OpenSSL 后运行 `bash tests/create-fixtures.sh`；
运行检查直接使用已提交样本，不需要完整 FFmpeg CLI。

Linux amd64 / ARM64 的候选 CI 还检出工作流固定 SHA 的 DDBOT 消费方，
将本次候选头文件与静态库安装到 `ffmpeg/ffmpeg-static`，使用 `ffmpeg_minimal` 构建标签
省略候选已移除的 x264 链接。DDBOT 的默认构建继续兼容现有正式库。

`consumer/fixtures_test.go` 注入该检出目录，使用 `DDBOT_FFMPEG_FIXTURES` 指向 `data/`。
三种 HLS 各转 MP4 / GIF，共 6 项；MP4 检查音视频双轨和封装元素，GIF 解码后检查动画帧。
同时运行 DDBOT 自身 FFmpeg 包的选流、截断输入、失败清理、超时及日志级别回归。

随后构建完整 DDBOT，记录源码 SHA、Go 版本、ELF 架构、文件大小、动态依赖及 GLIBC
符号版本，并生成可独立校验的 SHA-256。`consumer/dependencies.py` 拒绝缺失依赖或意外
动态链接的 FFmpeg / OpenSSL / x264，并要求最高 GLIBC 符号版本不超过 2.35。
两种 Linux 架构均使用 Ubuntu 22.04 用户空间构建；ARM64 在原生 runner 上使用该容器，
避免新宿主系统提高动态链接基线。符号检查不替代具体旧系统上的完整运行验收。
macOS / Windows CI 当前验证库能力、网络读取和迁移链接；完整消费方验证范围另见验证记录。
