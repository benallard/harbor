class Config:
    backend = "caddy"
    host = "0.0.0.0"
    port = 8080
    caddy_admin = "http://127.0.0.1:2019"
    static_dir = "/etc/harbor/service.d"
