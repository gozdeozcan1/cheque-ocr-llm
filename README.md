# Cheque Field Extraction with OCR and a Local LLM

A Python learning project that extracts cheque dates, payees, and amounts using Tesseract OCR and a local Qwen model through Ollama. It preserves original OCR readings, records model proposals separately, checks supporting OCR evidence, and routes uncertain results to human review.

## Pipeline

1. Select unique local image files by SHA-256 hash.
2. Crop date, payee, and amount regions; apply grayscale, resizing, contrast adjustment, and threshold variants.
3. Run multiple Tesseract segmentation modes and select candidates using OCR confidence and field-format checks.
4. Supply OCR text, alternative readings, full-page OCR, and the written amount to the local LLM.
5. Request structured JSON with values and evidence fragments.
6. Validate formats and OCR evidence, keep fallback readings where needed, and save review reasons.
7. Compare OCR, model proposals, and final output against a separate reference CSV.

The LLM receives OCR text, not images. This is a text-based OCR/LLM extraction pipeline; it does not train a new language model and does not use RAG.

## Dataset

Source: [ashishkamra79/bofa_cheques on Hugging Face](https://huggingface.co/datasets/ashishkamra79/bofa_cheques). The dataset card describes synthetic cheque data. Images and reference labels are not included in this repository.

For the recorded experiment, 100 unique images were selected from the downloaded data. Hash deduplication compares exact file bytes; it is not perceptual image deduplication. The downloader used for the original experiment is not included. Place your existing extracted images under `data/images/`; preserve filenames when matching labels.

The crop coordinates target this cheque layout. They need adjustment for other bank formats, rotations, or layouts.

## Recorded results

Final local run: 100 checks, model `qwen2.5:3b`, followed by cached amount evidence revalidation.

| Metric | OCR baseline | LLM proposal | Final output |
|---|---:|---:|---:|
| Date accuracy | 85% | 85% | 85% |
| Payee accuracy | 57% | 68% | 68% |
| Amount accuracy | 72% | 80% | 79% |
| All three fields correct | 40% | 51% | 50% |

The final output corrected 18 field errors without regressing an originally correct field in this experiment. Reference dates were compared exactly, payees with case/whitespace normalization (punctuation retained), and amounts with Decimal comparison. Reference labels were supplied separately by the project owner and were not sent to the LLM.

98 checks were routed to review and 2 were marked extracted. Both extracted checks matched all three reference fields, but a two-check automatic subset does not establish reliable automatic verification. This is a conservative prototype with a high review rate. The confidence threshold of 80 is an uncalibrated OCR-score cutoff, not an 80% probability of correctness.

These are development-set results; an independent held-out evaluation was not performed. `benchmarks/evaluation_summary.json` contains aggregate counts. No claim of production readiness or 100% extraction accuracy is made.

## Setup on Windows

Install Python, Tesseract with English language data, and Ollama separately. Tesseract is discovered on PATH or at `C:\Program Files\Tesseract-OCR\tesseract.exe`.

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull qwen2.5:3b
```

Keep Ollama running. Directly calling the virtual environment's Python avoids requiring activation.

## Run

Run commands from the project folder after placing images under `data/images/`:

```bat
.venv\Scripts\python.exe prepare_selection.py
.venv\Scripts\python.exe read_cheques_core.py --limit 10
.venv\Scripts\python.exe run_cheques_llm.py --limit 10 --outputs outputs/llm
```

For all selected images use `--limit 0` on both the OCR and LLM commands. The selection helper selects every unique local image; it does not force a count of 100.

CSV output uses semicolon separators and UTF-8 BOM for Excel compatibility. `extracted` means a model extraction passed current rules, not that a human verified it. Review flags should not be changed using reference labels in the extraction path.

### Evaluate

Place a reference CSV at `data/ground_truth.csv` with unique `filename` keys and columns `date`, `payee`, and `amount`. Use dates in MM/DD/YYYY and decimal amounts such as 2226.06. The program evaluates automatically when the file exists, or run:

```bat
.venv\Scripts\python.exe run_cheques_llm.py --evaluate-only --outputs outputs/llm --labels data/ground_truth.csv
```

Reference values belong to evaluation only. Do not generate ground truth by copying predictions.

### Revalidate saved amount proposals

Saved `*_input.json` and `*_response.json` files allow evidence checks without another OCR/model run:

```bat
.venv\Scripts\python.exe recheck_saved_amounts.py --results outputs/llm/cheque_llm_results.csv --saved-json outputs/llm --output outputs/llm_final/cheque_llm_results.csv
```

This checks stored inputs against the result baseline, preserves the original CSV, and retains human-review flags. It updates supported amount proposals only; it is not a new model inference.

## Evidence and limitations

Exact evidence quotations are checked against the original OCR strings. Amounts can also be supported by an explicit decimal currency token in the OCR text. A missing decimal point is not inserted solely because a reference label would make it correct. Text support does not prove a value was correctly read from the image or attached to the right field.

OCR confidence, invalid formats, and conflicting usable alternatives trigger review. Several variants can share the same recognition error; agreement is not independent verification. Handwritten payee recognition remains a limitation. The model does not reliably recover every missing digit or name.

The supplied OCR source records confidence and alternatives; the original LLM runner was extended with review propagation, evidence checks, and an offline audit mode. Source files contain no comment lines; operational explanations are kept here.

## Validation

The owner completed the 100-check local run. Its saved result CSV was evaluated against the supplied reference. Code preparation checks covered Python syntax, evidence token matching (including substring rejection and thousands separators), policy boundaries, and preserved predictions during offline review. The cached amount revalidation was run locally by the owner and the final uploaded CSV was checked.

The complete OCR/Ollama pipeline was not independently rerun in the packaging environment. Python, Tesseract, Ollama versions and machine specifications for the measured run were not captured; timings and environment reproducibility are therefore not reported.

## Files

- `prepare_selection.py`: exact-byte image deduplication and selection CSV.
- `read_cheques_core.py`: layout-based OCR and candidate extraction.
- `run_cheques_llm.py`: local LLM extraction, evidence/review policy, and evaluation.
- `recheck_saved_amounts.py`: cached amount evidence revalidation.
- `requirements.txt`: Python dependency; Tesseract and Ollama are separate installations.
- `benchmarks/evaluation_summary.json`: aggregate measured results.

No open-source code license has been selected. Dataset usage follows the source dataset's terms.
