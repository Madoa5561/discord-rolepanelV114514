# discord-roleepanelV114514
認証パネルv3というbotがサービス終了するらしいので代用を

## install

[https://discord.com/oauth2/authorize?client_id=1350516067004453036&permissions=268790848&integration_type=0&scope=bot](https://discord.com/oauth2/authorize?client_id=1350516067004453036&permissions=8&integration_type=0&scope=bot)

> [!WARNING]
> 謎に権限設定してもmissingPermissionが出るので管理者権限になってます
> TOKENが漏れることは絶対にありませんが、一応selfHostingを推奨しています

> [!IMPORTANT]
> 不具合や問題が発生した場合は
> https://x.com/shota5561 まで

## selfHosting
```python3 -m venv env```
```pip install discord```
```python3 main.py```
