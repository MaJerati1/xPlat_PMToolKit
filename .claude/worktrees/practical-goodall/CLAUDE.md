# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**xPlat PMToolKit** is an AI-powered PM toolkit that processes meeting transcripts to help teams prepare for meetings and auto-generate next steps. Users provide a transcript; the system produces structured outputs.

## Key Architecture Concept: LLM Data Isolation Tiers

The system is designed around three configurable data isolation tiers, swappable per project or workspace:

- **Tier 1** — Cloud API with zero-retention policy (e.g., OpenAI/Anthropic with zero-data-retention agreements)
- **Tier 2** — Pre-processing redaction of sensitive identifiers before sending to cloud LLM
- **Tier 3** — Self-hosted / private LLM for fully air-gapped processing

This tiered isolation model is a core architectural constraint. Any LLM integration code must be designed to swap the backend without changing the processing logic.

## Current State

This repository is in early/pre-code stage. No implementation exists yet — only this README and CLAUDE.md.
