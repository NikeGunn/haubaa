"""Tests for daemon autostart module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hauba.daemon.autostart import (
    SERVICE_NAME,
    _find_hauba_binary,
    install_autostart,
    is_installed,
    uninstall_autostart,
)


class TestFindHaubaBinary:
    """Test finding the hauba binary."""

    def test_fallback_to_python_m(self) -> None:
        result = _find_hauba_binary()
        # Should return something (either a path or python -m hauba)
        assert result is not None
        assert "hauba" in result


class TestInstallAutostart:
    """Test auto-start installation."""

    @patch("hauba.daemon.autostart._find_hauba_binary", return_value=None)
    def test_install_no_binary(self, _mock_find: MagicMock) -> None:
        result = install_autostart()
        assert result is False

    @patch("hauba.daemon.autostart._find_hauba_binary", return_value="/usr/bin/hauba")
    def test_install_windows(self, _mock_find: MagicMock) -> None:
        with patch("hauba.daemon.autostart.sys") as mock_sys:
            mock_sys.platform = "win32"
            with patch(
                "hauba.daemon.autostart._install_windows", return_value=True
            ) as mock_install:
                result = install_autostart(server_url="https://test.com")
                assert result is True
                mock_install.assert_called_once()

    @patch("hauba.daemon.autostart._find_hauba_binary", return_value="/usr/bin/hauba")
    def test_install_macos(self, _mock_find: MagicMock) -> None:
        with patch("hauba.daemon.autostart.sys") as mock_sys:
            mock_sys.platform = "darwin"
            with patch("hauba.daemon.autostart._install_macos", return_value=True) as mock_install:
                result = install_autostart()
                assert result is True
                mock_install.assert_called_once()

    @patch("hauba.daemon.autostart._find_hauba_binary", return_value="/usr/bin/hauba")
    def test_install_linux(self, _mock_find: MagicMock) -> None:
        with patch("hauba.daemon.autostart.sys") as mock_sys:
            mock_sys.platform = "linux"
            with patch("hauba.daemon.autostart._install_linux", return_value=True) as mock_install:
                result = install_autostart()
                assert result is True
                mock_install.assert_called_once()


class TestUninstallAutostart:
    """Test auto-start uninstallation."""

    def test_uninstall_windows(self) -> None:
        with patch("hauba.daemon.autostart.sys") as mock_sys:
            mock_sys.platform = "win32"
            with patch(
                "hauba.daemon.autostart._uninstall_windows", return_value=True
            ) as mock_uninstall:
                result = uninstall_autostart()
                assert result is True
                mock_uninstall.assert_called_once()

    def test_uninstall_linux(self) -> None:
        with patch("hauba.daemon.autostart.sys") as mock_sys:
            mock_sys.platform = "linux"
            with patch(
                "hauba.daemon.autostart._uninstall_linux", return_value=True
            ) as mock_uninstall:
                result = uninstall_autostart()
                assert result is True
                mock_uninstall.assert_called_once()


class TestIsInstalled:
    """Test checking if autostart is installed."""

    def test_not_installed_windows(self) -> None:
        with patch("hauba.daemon.autostart.sys") as mock_sys:
            mock_sys.platform = "win32"
            with patch("hauba.daemon.autostart._is_installed_windows", return_value=False):
                assert is_installed() is False

    def test_installed_windows(self) -> None:
        with patch("hauba.daemon.autostart.sys") as mock_sys:
            mock_sys.platform = "win32"
            with patch("hauba.daemon.autostart._is_installed_windows", return_value=True):
                assert is_installed() is True


class TestServiceName:
    """Test service constants."""

    def test_service_name(self) -> None:
        assert SERVICE_NAME == "hauba-agent"
