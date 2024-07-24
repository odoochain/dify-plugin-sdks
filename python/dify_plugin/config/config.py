from enum import Enum
from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict


class InstallMethod(Enum):
    Local = "local"
    Remote = "remote"
    AWSLambda = "aws_lambda"


class DifyPluginEnv(BaseModel):
    MAX_REQUEST_TIMEOUT: int = Field(
        default=300, description="Maximum request timeout in seconds"
    )
    MAX_WORKER: int = Field(
        default=1000,
        description="Maximum worker count, gevent will be used for async IO"
        "and you dont need to worry about the thread count",
    )
    HEARTBEAT_INTERVAL: float = Field(
        default=10, description="Heartbeat interval in seconds"
    )
    INSTALL_METHOD: InstallMethod = Field(
        default=InstallMethod.Local,
        description="Installation method, local or network",
    )

    REMOTE_INSTALL_HOST: str = Field(
        default="localhost", description="Remote installation host"
    )
    REMOTE_INSTALL_PORT: int = Field(
        default=5003, description="Remote installation port"
    )

    model_config = SettingsConfigDict(
        # read from dotenv format config file
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
        # ignore extra attributes
        extra="ignore",
    )
