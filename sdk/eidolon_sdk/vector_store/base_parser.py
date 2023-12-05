import contextlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BufferedReader, BytesIO, IOBase
from typing import Union, Optional, Generator, Sequence

from pydantic import BaseModel

from eidolon_sdk.reference_model import Specable
from eidolon_sdk.vector_store.document import Document


@dataclass
class DataBlob:
    data: Union[bytes, IOBase, str, None]
    mimetype: Optional[str] = None
    encoding: str = "utf-8"
    path: Optional[str] = None

    @contextlib.contextmanager
    def as_bytes(self) -> Generator[Union[BytesIO, BufferedReader], None, None]:
        if isinstance(self.data, bytes):
            yield BytesIO(self.data)
        elif isinstance(self.data, IOBase):
            yield self.data
        elif isinstance(self.data, str):
            yield BytesIO(self.data.encode(self.encoding))
        elif self.data is None and self.path:
            with open(str(self.path), "rb") as f:
                yield f
        else:
            raise TypeError("DataBlob.data must be bytes or str")

    def as_string(self) -> str:
        if self.data is None and self.path:
            with open(str(self.path), "r", encoding=self.encoding) as f:
                self.data = f.read()
                return self.data
        elif isinstance(self.data, bytes):
            return self.data.decode(self.encoding)
        elif isinstance(self.data, str):
            return self.data
        else:
            raise TypeError("DataBlob.data must be bytes or str")

    @classmethod
    def from_path(
        cls,
        path: str,
        *,
        encoding: str = "utf-8",
        mimetype: Optional[str] = None,
        guess_type: bool = True
    ) -> "DataBlob":
        """Load the blob from a path like object.

        Args:
            path: path like object to file to be read
            encoding: Encoding to use if decoding the bytes into a string
            mimetype: if provided, will be set as the mime-type of the data
            guess_type: If True, the mimetype will be guessed from the contents of the file,
                        if a mime-type was not provided

        Returns:
            Blob instance
        """
        if guess_type and mimetype is None:
            import filetype
            mimetype = filetype.guess_mime(path)

        return cls(
            data=None,
            path=path,
            encoding=encoding,
            mimetype=mimetype,
        )

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        *,
        path: Optional[str],
        mimetype: Optional[str] = None,
        encoding: str = "utf-8",
        guess_type: bool = True
    ) -> "DataBlob":
        """Load the blob from a bytes object.

        Args:
            data: bytes object to be read
            path: path to file that the bytes object was read from or None if not applicable
            mimetype: if provided, will be set as the mime-type of the data
            encoding: Encoding to use if decoding the bytes into a string
            guess_type: If True, the mimetype will be guessed from the contents of the data,
                        if a mime-type was not provided

        Returns:
            Blob instance
        """
        if guess_type and mimetype is None:
            import filetype
            mimetype = filetype.guess_mime(data)

        return cls(
            data=data,
            path=path,
            encoding=encoding,
            mimetype=mimetype,
        )

    @classmethod
    def from_bytes_buffer(
        cls,
        data: IOBase,
        *,
        path: Optional[str],
        mimetype: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> "DataBlob":
        """Load the blob from a bytes object.

        Args:
            data: bytes object to be read
            path: path to file that the bytes object was read from or None if not applicable
            mimetype: if provided, will be set as the mime-type of the data
            encoding: Encoding to use if decoding the bytes into a string

        Returns:
            Blob instance
        """
        return cls(
            data=data,
            path=path,
            encoding=encoding,
            mimetype=mimetype,
        )

    @classmethod
    def from_string(
        cls,
        data: str,
        *,
        path: Optional[str],
        mimetype: Optional[str] = None,
        encoding: str = "utf-8"
    ) -> "DataBlob":
        """Load the blob from a string object.

        Args:
            data: string object to be read
            path: path to file that the string object was read from or None if not applicable
            mimetype: if provided, will be set as the mime-type of the data
            encoding: Encoding to use if decoding the bytes into a string

        Returns:
            Blob instance
        """
        return cls(
            data=data,
            path=path,
            encoding=encoding,
            mimetype=mimetype,
        )


class BaseParserSpec(BaseModel):
    pass


class BaseParser(ABC, Specable[BaseParserSpec]):
    def __init__(self, spec: BaseParserSpec):
        self.spec = spec
        self.logger = logging.getLogger("eidolon")

    @abstractmethod
    def parse(self, blob: DataBlob) -> Sequence[Document]:
        pass