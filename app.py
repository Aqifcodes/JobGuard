from __future__ import annotations

import traceback
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from agent.graph import run_investigation
from agent.nodes.input_processor import process_input
from job_discovery.service import JobDiscoveryService

job_discovery_service = JobDiscoveryService()




BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "web" / "templates"),
    static_folder=str(BASE_DIR / "web" / "static"),
)

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# ============================================================
# PAGES
# ============================================================

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/results")
def results():
    return render_template("results.html")


# ============================================================
# ANALYZE API
# ============================================================

@app.post("/analyze")
def analyze():
    try:

        # ----------------------------------------------------
        # Detect which input was submitted
        # ----------------------------------------------------

        text = request.form.get("text", "").strip()
        url = request.form.get("url", "").strip()
        uploaded_file = request.files.get("file")

        # ----------------------------------------------------
        # TEXT INPUT
        # ----------------------------------------------------

        if text:

            investigation_input = process_input(
                text=text
            )

        # ----------------------------------------------------
        # URL INPUT
        # ----------------------------------------------------

        elif url:

            investigation_input = process_input(
                text=url
            )

        # ----------------------------------------------------
        # FILE INPUT
        # ----------------------------------------------------

        elif uploaded_file and uploaded_file.filename:

            file_bytes = uploaded_file.read()

            if not file_bytes:
                return jsonify({
                    "success": False,
                    "error": "The selected file is empty."
                }), 400

            investigation_input = process_input(
                file_bytes=file_bytes,
                file_name=uploaded_file.filename,
            )

        # ----------------------------------------------------
        # NOTHING PROVIDED
        # ----------------------------------------------------

        else:

            return jsonify({
                "success": False,
                "error": "Please provide a job posting, URL, or file."
            }), 400

        # ----------------------------------------------------
        # RUN COMPLETE PIPELINE
        # ----------------------------------------------------

        result = run_investigation(
            investigation_input
        )

        # ----------------------------------------------------
        # GATE 5
        # ----------------------------------------------------

        gate5 = result.get("gate_5", {})

        # Some graph implementations may return the
        # dataclass directly instead of a dictionary.
        if hasattr(gate5, "to_dict"):
            gate5 = gate5.to_dict()

        if not isinstance(gate5, dict):
            gate5 = {}

        # ----------------------------------------------------
        # USER-FACING RESPONSE
        #
        # Gates 1-4 remain completely internal.
        # The UI receives only the final assessment data.
        # ----------------------------------------------------

        response = {
            "success": True,

            "assessment": gate5.get(
                "assessment",
                "INCONCLUSIVE"
            ),

            "confidence": gate5.get(
                "confidence",
                0.0
            ),

            "reasoning": gate5.get(
                "reasoning",
                []
            ),

            "recommendations": gate5.get(
                "recommendations",
                []
            ),

            "supporting_evidence": gate5.get(
                "supporting_evidence",
                []
            ),

            "contradicting_evidence": gate5.get(
                "contradicting_evidence",
                []
            ),

            "warnings": gate5.get(
                "warnings",
                []
            ),
        }

        return jsonify(response)

    except Exception as exc:

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.route("/api/jobs/search", methods=["POST"])
def search_jobs():
    try:
        data = request.get_json(silent=True) or {}

        role = str(data.get("role", "")).strip()
        location = str(data.get("location", "")).strip()
        experience = str(data.get("experience", "")).strip()

        if not role:
            return jsonify({
                "success": False,
                "error": "Please select a job role."
            }), 400

        result = job_discovery_service.find_jobs(
            role=role,
            location=location,
            experience=experience,
        )

        return jsonify(result), 200

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception as exc:
        app.logger.exception("Job search failed")

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500

@app.route("/jobs")
def jobs_page():
    return render_template("jobs.html")


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    return jsonify({
        "status": "ok"
    })


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )