from flask import Blueprint, request, jsonify

from src.services.summary_service import generate_summary

summary_bp = Blueprint("summary", __name__, url_prefix="/ai")


@summary_bp.route("/summary", methods=["POST"])
def summarize():

    try:

        data = request.get_json()

        text = data.get("text", "")

        if not text:

            return jsonify({"error": "No text provided"}), 400

        summary = generate_summary(text)

        return jsonify({"summary": summary})

    except Exception as e:

        return jsonify({"error": str(e)}), 500
