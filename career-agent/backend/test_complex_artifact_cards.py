from __future__ import annotations

from types import SimpleNamespace

from app.services.agent_orchestrator_service import AgentOrchestratorService


def _resume_tool_output() -> dict:
    return {
        "tool": "optimize_resume",
        "title": "Resume Optimize",
        "summary": "Resume optimization completed.",
        "data": {
            "attachment_name": "李悦 - 应届Java后端开发工程师简历.docx",
            "editable_word_url": "/uploads/resume_exports/student_1/student_1_attachment_7_optimized_resume.docx",
            "editable_word_path": r"D:\app\uploads\resume_exports\student_1\student_1_attachment_7_optimized_resume.docx",
            "optimized_pdf_url": "/uploads/resume_exports/student_1/student_1_attachment_7_optimized_resume.pdf",
            "optimized_pdf_path": r"D:\app\uploads\resume_exports\student_1\student_1_attachment_7_optimized_resume.pdf",
        },
    }


def test_complex_response_promotes_resume_exports_to_artifacts() -> None:
    service = AgentOrchestratorService.__new__(AgentOrchestratorService)
    service.card_factory = SimpleNamespace(build_many=lambda tool_outputs: [])
    service.state_service = SimpleNamespace(merge=lambda *args, **kwargs: {"merged": True})

    result = service._pack_complex_response(
        state={
            "plan": {"intent": "resume_optimization", "selected_skill": "resume-workbench", "normalized_skill": "resume-workbench"},
            "reply": "\n".join(
                [
                    "## 结论",
                    "简历优化已完成，Word文档已生成并可下载。",
                    "",
                    "**文件获取方式：**",
                    "- Word版：`/uploads/resume_exports/student_1/student_1_attachment_7_optimized_resume.docx`",
                    "- PDF版：`/uploads/resume_exports/student_1/student_1_attachment_7_optimized_resume.pdf`",
                    "",
                    "---",
                    "",
                    "## 依据",
                    "优化前问题诊断已完成。",
                ]
            ),
            "tool_outputs": [_resume_tool_output(), _resume_tool_output()],
            "tool_steps": [{"tool": "optimize_resume", "status": "done"}],
        }
    )

    artifacts = result["artifacts"]
    assert len(artifacts) == 2
    assert artifacts[0]["download_url"].endswith(".docx")
    assert artifacts[0]["mime_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert artifacts[1]["download_url"].endswith(".pdf")
    assert artifacts[1]["mime_type"] == "application/pdf"
    assert "文件获取方式" not in result["reply"]
    assert "/uploads/resume_exports/" not in result["reply"]
    assert "## 依据" in result["reply"]


def test_complex_artifact_extraction_uses_path_when_url_missing() -> None:
    output = _resume_tool_output()
    data = output["data"]
    data["editable_word_url"] = ""
    data["optimized_pdf_url"] = ""

    artifacts = AgentOrchestratorService._extract_artifacts_from_tool_outputs([output])

    assert [item["download_url"] for item in artifacts] == [
        "/uploads/resume_exports/student_1/student_1_attachment_7_optimized_resume.docx",
        "/uploads/resume_exports/student_1/student_1_attachment_7_optimized_resume.pdf",
    ]
