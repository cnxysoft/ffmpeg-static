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

这些检查覆盖静态库能力和网络读取。MP4 选流、转封装、GIF 动画、失败文件清理、
超时及 DD 日志行为，仍需在 DDBOT 消费方使用配套候选库运行 `go test ./ffmpeg`。
