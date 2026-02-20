from src import app
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfigs(BaseSettings):
    port: int
    host: str

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False
    )


def main():
    """Run the FastMCP HTTP server."""
    config = ServerConfigs() #type: ignore
    
    app.run(transport="http", host=config.host, port=config.port)


if __name__ == "__main__":
    main()