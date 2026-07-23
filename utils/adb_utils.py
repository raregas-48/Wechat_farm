"""
ADB 工具模块 — 封装常用 ADB 命令，用于设备诊断和管理。

使用方式:
    from utils.adb_utils import ADBUtils
    devices = ADBUtils.list_devices()
"""

import subprocess
import time
from typing import Optional

from utils.logger import get_logger

logger = get_logger("adb_utils")


class ADBUtils:
    """ADB 命令封装（静态方法集合）"""

    ADB_PATH = "adb"

    @classmethod
    def list_devices(cls) -> list[str]:
        """
        列出所有已连接的 Android 设备。

        Returns:
            设备序列号列表
        """
        result = subprocess.run(
            [cls.ADB_PATH, "devices"],
            capture_output=True, text=True,
        )
        lines = result.stdout.strip().split("\n")[1:]
        devices = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices

    @classmethod
    def get_device_state(cls, serial: str) -> str:
        """
        获取设备连接状态。

        Returns:
            "device" | "offline" | "unauthorized" | "unknown"
        """
        result = subprocess.run(
            [cls.ADB_PATH, "-s", serial, "get-state"],
            capture_output=True, text=True,
        )
        return result.stdout.strip()

    @classmethod
    def is_device_online(cls, serial: str) -> bool:
        """检查设备是否在线"""
        return cls.get_device_state(serial) == "device"

    @classmethod
    def get_device_info(cls, serial: str) -> dict:
        """
        获取设备基本信息（型号、Android 版本、SDK 级别）。

        Returns:
            {"model": "...", "brand": "...", "android_version": "...", "sdk": "..."}
        """
        info = {}
        props = {
            "model": "ro.product.model",
            "brand": "ro.product.brand",
            "android_version": "ro.build.version.release",
            "sdk": "ro.build.version.sdk",
        }
        for key, prop in props.items():
            result = subprocess.run(
                [cls.ADB_PATH, "-s", serial, "shell", "getprop", prop],
                capture_output=True, text=True,
            )
            info[key] = result.stdout.strip()
        return info

    @classmethod
    def reboot_device(cls, serial: str) -> bool:
        """重启设备"""
        try:
            subprocess.run(
                [cls.ADB_PATH, "-s", serial, "reboot"],
                capture_output=True, timeout=10,
            )
            logger.info(f"设备 {serial} 正在重启...")
            return True
        except Exception as e:
            logger.error(f"重启设备 {serial} 失败: {e}")
            return False

    @classmethod
    def wait_for_device(cls, serial: str, timeout: float = 120.0) -> bool:
        """等待设备上线（重启后使用）"""
        logger.info(f"等待设备 {serial} 上线...")
        start = time.time()
        while time.time() - start < timeout:
            if cls.is_device_online(serial):
                logger.info(f"设备 {serial} 已上线")
                return True
            time.sleep(2)
        logger.error(f"设备 {serial} 在 {timeout}s 内未上线")
        return False

    @classmethod
    def restart_adb_server(cls) -> bool:
        """重启 ADB 服务（USB 连接异常时使用）"""
        try:
            subprocess.run([cls.ADB_PATH, "kill-server"], capture_output=True, timeout=5)
            time.sleep(1)
            subprocess.run([cls.ADB_PATH, "start-server"], capture_output=True, timeout=10)
            logger.info("ADB 服务已重启")
            return True
        except Exception as e:
            logger.error(f"重启 ADB 服务失败: {e}")
            return False
