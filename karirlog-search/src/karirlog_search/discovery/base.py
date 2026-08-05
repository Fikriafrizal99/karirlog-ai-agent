from __future__ import annotations

from abc import ABC, abstractmethod

from karirlog_contracts.job import Job


class JobSource(ABC):
    @abstractmethod
    def collect(self) -> list[Job]:
        raise NotImplementedError
