# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Normalized knowledge record schema for the STAF generated knowledge base.
"""

from enum import Enum
from typing import List, Literal
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class KnowledgeKind(str, Enum):
    """Category of a normalized knowledge record."""

    DIAGNOSTIC_PROBE = "diagnostic-probe"
    HA_FUNCTIONAL_TEST = "ha-functional-test"
    BACKUP_TEST = "backup-test"


class KnowledgeRisk(str, Enum):
    """Safety classification of the execution a record refers to."""

    READ_ONLY = "read-only"
    DESTRUCTIVE = "destructive"


class AppliesTo(BaseModel):
    """Optional applicability filters for a knowledge record.

    Each field is an explicit, deterministically-mapped list. An empty list
    means the source artifact did not restrict the record along that
    dimension; it is not evidence of universal applicability being inferred.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    component: List[str] = Field(default_factory=list)
    os_family: List[str] = Field(default_factory=list)
    topology: List[str] = Field(default_factory=list)


class KnowledgeRecord(BaseModel):
    """
    A single normalized, generated STAF knowledge record.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)
    schema_version: Literal["1.0"] = Field(default=SCHEMA_VERSION)
    id: str = Field(..., min_length=1, pattern=r"^[a-z0-9][a-z0-9.\-]*$")
    kind: KnowledgeKind
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    applies_to: AppliesTo = Field(default_factory=AppliesTo)
    provides: List[str] = Field(default_factory=list)
    risk: KnowledgeRisk
    execution_ref: str = Field(..., min_length=1)
    source_ref: str = Field(..., min_length=1)
    source_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")


class SearchResult(BaseModel):
    """A single generated-knowledge search hit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    description: str
    kind: str
    risk: str
    provides: List[str]
    source_ref: str
    rank: float = Field(description="FTS5 rank score; lower is a better match")


class SearchResponse(BaseModel):
    """Generated-knowledge search response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    results: List[SearchResult]
    total_matched: int = Field(description="Total matches before applying the limit")
