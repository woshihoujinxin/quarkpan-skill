"""
认证管理命令
"""

import typer
from rich import print as rprint

from ..utils import get_client, print_error, print_info, print_success

auth_app = typer.Typer(help="🔐 认证管理")


@auth_app.callback(invoke_without_command=True)
def auth_default(ctx: typer.Context):
    """🔐 认证管理 - 默认生成二维码登录"""
    if ctx.invoked_subcommand is None:
        ctx.invoke(qr)


@auth_app.command()
def qr():
    """生成登录二维码图片（第一步）

    生成二维码图片并打开，用夸克APP扫描后执行 quarkpan auth poll 完成登录。
    """
    try:
        from quark_client.auth.api_login import APILogin
        api = APILogin()
        qr_url = api.generate_qr()

        rprint("[bold blue]🔐 登录二维码已生成[/bold blue]")
        rprint(f"\n  [bold green]{qr_url}[/bold green]\n")
        rprint("用夸克APP扫描二维码图片，然后执行:")
        rprint("  [cyan]quarkpan auth poll[/cyan]")
    except Exception as e:
        print_error(f"生成二维码失败: {e}")
        raise typer.Exit(1)


@auth_app.command()
def poll():
    """轮询登录状态（第二步）

    在执行 quarkpan auth qr 并扫码后，执行此命令完成登录。
    """
    try:
        from quark_client.auth.api_login import APILogin
        from quark_client.auth.login import QuarkAuth

        api = APILogin()
        cookies = api.poll_login()

        if cookies:
            auth = QuarkAuth()
            cookie_list = auth._parse_cookie_string(cookies)
            auth._save_cookies(cookie_list)
            print_success("登录成功！")
        else:
            rprint("[yellow]⏳ 尚未扫码或正在等待确认，请稍后再试[/yellow]")
            rprint("执行 [cyan]quarkpan auth poll[/cyan] 再次检查")
    except Exception as e:
        print_error(f"登录失败: {e}")
        raise typer.Exit(1)


@auth_app.command()
def login(
    force: bool = typer.Option(False, "--force", "-f", help="强制重新登录"),
):
    """🔐 交互式登录（终端显示二维码并等待扫码）

    在终端显示ASCII二维码并阻塞等待扫码完成，适合人在终端操作。
    """
    try:
        with get_client(auto_login=False) as client:
            if not force and client.is_logged_in():
                rprint("[green]✅ 已经登录，无需重复登录[/green]")
                rprint("使用 [cyan]--force[/cyan] 强制重新登录")
                return

            cookies = client.login(force_relogin=force, method="api")

            if cookies:
                print_success("登录成功！")
                if client.is_logged_in():
                    print_info("登录状态验证通过")
            else:
                print_error("登录失败，未获取到有效凭证")
                raise typer.Exit(1)

    except KeyboardInterrupt:
        rprint("\n[yellow]⚠️ 登录被用户取消[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"登录失败: {e}")
        raise typer.Exit(1)


@auth_app.command()
def logout():
    """登出夸克网盘"""
    try:
        with get_client(auto_login=False) as client:
            if not client.is_logged_in():
                rprint("[yellow]⚠️ 当前未登录[/yellow]")
                return

            print_info("正在登出...")
            client.logout()
            print_success("已成功登出")

    except Exception as e:
        print_error(f"登出失败: {e}")
        raise typer.Exit(1)


@auth_app.command()
def status():
    """检查登录状态"""
    try:
        with get_client(auto_login=False) as client:
            if client.is_logged_in():
                print_success("已登录")

                try:
                    storage = client.get_storage_info()
                    if storage and 'data' in storage:
                        data = storage['data']
                        total = data.get('total', 0)
                        used = data.get('used', 0)

                        from ..utils import format_file_size

                        rprint(f"[dim]总容量: {format_file_size(total)}[/dim]")
                        rprint(f"[dim]已使用: {format_file_size(used)}[/dim]")
                        rprint(f"[dim]剩余: {format_file_size(total - used)}[/dim]")
                    else:
                        rprint("[yellow]⚠️ 无法获取存储信息[/yellow]")
                except Exception as e:
                    rprint(f"[yellow]⚠️ 获取存储信息失败: {e}[/yellow]")
            else:
                rprint("[red]❌ 未登录[/red]")
                rprint("使用 [cyan]quarkpan auth[/cyan] 登录")
                raise typer.Exit(1)

    except Exception as e:
        print_error(f"检查状态失败: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    auth_app()
