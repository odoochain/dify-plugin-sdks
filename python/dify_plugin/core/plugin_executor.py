import binascii
from collections.abc import Generator, Iterable
import tempfile

from werkzeug import Response

from ..config.config import DifyPluginEnv
from .entities.plugin.request import (
    ModelGetAIModelSchemas,
    ModelGetLLMNumTokens,
    ModelGetTTSVoices,
    ModelGetTextEmbeddingNumTokens,
    ModelInvokeLLMRequest,
    ModelInvokeModerationRequest,
    ModelInvokeRerankRequest,
    ModelInvokeSpeech2TextRequest,
    ModelInvokeTTSRequest,
    ModelInvokeTextEmbeddingRequest,
    ModelValidateModelCredentialsRequest,
    ModelValidateProviderCredentialsRequest,
    ToolInvokeRequest,
    ToolValidateCredentialsRequest,
    EndpointInvokeRequest,
)
from ..interfaces.endpoint import Endpoint
from ..interfaces.model.large_language_model import LargeLanguageModel
from ..interfaces.model.moderation_model import ModerationModel
from ..interfaces.model.rerank_model import RerankModel
from ..interfaces.model.speech2text_model import Speech2TextModel
from ..interfaces.model.text_embedding_model import TextEmbeddingModel
from ..interfaces.model.tts_model import TTSModel
from ..core.plugin_registration import PluginRegistration
from ..entities.tool import ToolRuntime
from ..core.utils.http_parser import parse_raw_request
from ..core.runtime import Session


class PluginExecutor:
    def __init__(self, config: DifyPluginEnv, registration: PluginRegistration) -> None:
        self.config = config
        self.registration = registration

    def validate_tool_provider_credentials(
        self, session: Session, data: ToolValidateCredentialsRequest
    ):
        provider_instance = self.registration.get_tool_provider_cls(data.provider)
        if provider_instance is None:
            raise ValueError(f"Provider `{data.provider}` not found")

        provider_instance = provider_instance()

        try:
            provider_instance.validate_credentials(data.credentials)
        except Exception as e:
            raise ValueError(
                f"Failed to validate provider credentials: {type(e).__name__}: {str(e)}"
            )

        return {"result": True}

    def invoke_tool(self, session: Session, request: ToolInvokeRequest):
        provider_cls = self.registration.get_tool_provider_cls(request.provider)
        if provider_cls is None:
            raise ValueError(f"Provider `{request.provider}` not found")

        tool_cls = self.registration.get_tool_cls(request.provider, request.tool)
        if tool_cls is None:
            raise ValueError(
                f"Tool `{request.tool}` not found for provider `{request.provider}`"
            )

        # instantiate tool
        tool = tool_cls(
            runtime=ToolRuntime(
                credentials=request.credentials,
                user_id=request.user_id,
                session_id=session.session_id,
            ),
            session=session,
        )

        # invoke tool
        try:
            yield from tool.invoke_from_executor(request.tool_parameters)
        except Exception as e:
            raise ValueError(f"Failed to invoke tool: {type(e).__name__}: {str(e)}")

    def validate_model_provider_credentials(
        self, session: Session, data: ModelValidateProviderCredentialsRequest
    ):
        provider_instance = self.registration.get_model_provider_instance(data.provider)
        if provider_instance is None:
            raise ValueError(f"Provider `{data.provider}` not found")

        try:
            provider_instance.validate_provider_credentials(data.credentials)
        except Exception as e:
            raise ValueError(
                f"Failed to validate provider credentials: {type(e).__name__}: {str(e)}"
            )

        return {"result": True}

    def validate_model_credentials(
        self, session: Session, data: ModelValidateModelCredentialsRequest
    ):
        provider_instance = self.registration.get_model_provider_instance(data.provider)
        if provider_instance is None:
            raise ValueError(f"Provider `{data.provider}` not found")

        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )
        if model_instance is None:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

        try:
            model_instance.validate_credentials(data.model, data.credentials)
        except Exception as e:
            raise ValueError(
                f"Failed to validate model credentials: {type(e).__name__}: {str(e)}"
            )

        return {"result": True}

    def invoke_llm(self, session: Session, data: ModelInvokeLLMRequest):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )
        if isinstance(model_instance, LargeLanguageModel):
            return model_instance.invoke_from_executor(
                data.model,
                data.credentials,
                data.prompt_messages,
                data.model_parameters,
                data.tools,
                data.stop,
                data.stream,
                data.user_id,
            )
        else:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

    def get_llm_num_tokens(self, session: Session, data: ModelGetLLMNumTokens):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )
        if isinstance(model_instance, LargeLanguageModel):
            return {
                "num_tokens": model_instance.get_num_tokens(
                    data.model,
                    data.credentials,
                    data.prompt_messages,
                    data.tools,
                )
            }
        else:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

    def invoke_text_embedding(
        self, session: Session, data: ModelInvokeTextEmbeddingRequest
    ):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )
        if isinstance(model_instance, TextEmbeddingModel):
            return model_instance.invoke_from_executor(
                data.model,
                data.credentials,
                data.texts,
                data.user_id,
            )
        else:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

    def get_text_embedding_num_tokens(
        self, session: Session, data: ModelGetTextEmbeddingNumTokens
    ):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )
        if isinstance(model_instance, TextEmbeddingModel):
            return {
                "num_tokens": model_instance.get_num_tokens(
                    data.model,
                    data.credentials,
                    data.texts,
                )
            }
        else:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

    def invoke_rerank(self, session: Session, data: ModelInvokeRerankRequest):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )
        if isinstance(model_instance, RerankModel):
            return model_instance.invoke_from_executor(
                data.model,
                data.credentials,
                data.query,
                data.docs,
                data.score_threshold,
                data.top_n,
                data.user_id,
            )
        else:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

    def invoke_tts(self, session: Session, data: ModelInvokeTTSRequest):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )
        if isinstance(model_instance, TTSModel):
            b = model_instance.invoke_from_executor(
                data.model,
                data.credentials,
                data.content_text,
                data.voice,
                data.user_id,
            )
            if isinstance(b, bytes | bytearray | memoryview):
                return {"result": binascii.hexlify(b).decode()}

            for chunk in b:
                yield {"result": binascii.hexlify(chunk).decode()}
        else:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

    def get_tts_model_voices(self, session: Session, data: ModelGetTTSVoices):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )
        if isinstance(model_instance, TTSModel):
            return {
                "voices": model_instance.get_tts_model_voices(
                    data.model, data.credentials, data.language
                )
            }
        else:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

    def invoke_speech_to_text(
        self, session: Session, data: ModelInvokeSpeech2TextRequest
    ):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )

        with tempfile.NamedTemporaryFile(suffix=".mp3", mode="wb", delete=True) as temp:
            temp.write(binascii.unhexlify(data.file))
            temp.flush()

            with open(temp.name, "rb") as f:
                if isinstance(model_instance, Speech2TextModel):
                    return {
                        "result": model_instance.invoke_from_executor(
                            data.model,
                            data.credentials,
                            f,
                            data.user_id,
                        )
                    }
                else:
                    raise ValueError(
                        f"Model `{data.model_type}` not found for provider `{data.provider}`"
                    )

    def get_ai_model_schemas(self, session: Session, data: ModelGetAIModelSchemas):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )
        if isinstance(model_instance, LargeLanguageModel):
            return {
                "model_schema": model_instance.get_model_schema(
                    data.model, data.credentials
                )
            }
        else:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

    def invoke_moderation(self, session: Session, data: ModelInvokeModerationRequest):
        model_instance = self.registration.get_model_instance(
            data.provider, data.model_type
        )

        if isinstance(model_instance, ModerationModel):
            return {
                "result": model_instance.invoke_from_executor(
                    data.model,
                    data.credentials,
                    data.text,
                    data.user_id,
                )
            }
        else:
            raise ValueError(
                f"Model `{data.model_type}` not found for provider `{data.provider}`"
            )

    def invoke_endpoint(self, session: Session, data: EndpointInvokeRequest):
        bytes_data = binascii.unhexlify(data.raw_http_request)
        request = parse_raw_request(bytes_data)

        try:
            # dispatch request
            endpoint, values = self.registration.dispatch_endpoint_request(request)
            # construct response
            endpoint_instance: Endpoint = endpoint(session)
            response = endpoint_instance.invoke_from_executor(
                request, values, data.settings
            )
        except ValueError as e:
            response = Response(str(e), status=404)
        except Exception as e:
            response = Response(f"Internal Server Error: {str(e)}", status=500)

        # check if response is a generator
        if isinstance(response.response, Generator):
            # return headers
            yield {
                "status": response.status_code,
                "headers": {k: v for k, v in response.headers.items()},
            }

            for chunk in response.response:
                if isinstance(chunk, bytes | bytearray | memoryview):
                    yield {"result": binascii.hexlify(chunk).decode()}
                else:
                    yield {"result": binascii.hexlify(chunk.encode("utf-8")).decode()}
        else:
            result = {
                "status": response.status_code,
                "headers": {k: v for k, v in response.headers.items()},
            }

            if isinstance(response.response, bytes | bytearray | memoryview):
                result["result"] = binascii.hexlify(response.response).decode()
            elif isinstance(response.response, str):
                result["result"] = binascii.hexlify(
                    response.response.encode("utf-8")
                ).decode()
            elif isinstance(response.response, Iterable):
                result["result"] = ""
                for chunk in response.response:
                    if isinstance(chunk, bytes | bytearray | memoryview):
                        result["result"] += binascii.hexlify(chunk).decode()
                    else:
                        result["result"] += binascii.hexlify(
                            chunk.encode("utf-8")
                        ).decode()

            yield result
