from pathlib import Path
import re

root = Path("src")
client = root / "app/src/main/java/com/u1/slicer/printer/BambuLanClient.kt"
text = client.read_text(encoding="utf-8")

pattern = r"private val projectSubmissionId = AtomicInteger\(\s*\(System\.currentTimeMillis\(\) % Int\.MAX_VALUE\)\.toInt\(\)\.coerceAtLeast\(1\),\s*\)"
text, n = re.subn(
    pattern,
    'private val projectSubmissionId = AtomicInteger(20_000 + SecureRandom().nextInt(9_000))',
    text,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("projectSubmissionId patch failed")

needle = '        val firmwareVersion = firmwareVersion(config)\n        val command = "project_file"\n'
replacement = (
    '        val firmwareVersion = firmwareVersion(config)\n'
    '        if (developerMode(config) == false) {\n'
    '            throw IllegalStateException(\n'
    '                "Printer sync and upload work, but direct A1/A1 mini print-start is blocked because Developer Mode is off. " +\n'
    '                    "Enable Developer Mode in the printer LAN settings, refresh the access code, then retry.",\n'
    '            )\n'
    '        }\n'
    '        val command = "project_file"\n'
)
if needle not in text:
    raise SystemExit("developer-mode insertion anchor missing")
text = text.replace(needle, replacement, 1)

text = text.replace('.put("md5", "")', '.put("md5", "from_sd_card")', 1)
text = text.replace('.put("project_id", submissionId)', '.put("project_id", "0")', 1)
text = text.replace('.put("subtask_id", submissionId)', '.put("subtask_id", "0")', 1)
text = text.replace('.put("task_id", submissionId)', '.put("task_id", "0")', 1)

old_upload = '            return if (model == BambuModel.H2D) "/$name" else "/cache/$name"\n'
new_upload = (
    '            return when {\n'
    '                model == BambuModel.H2D || isASeries(model) -> "/$name"\n'
    '                else -> "/cache/$name"\n'
    '            }\n'
)
if old_upload not in text:
    raise SystemExit("projectUploadPath anchor missing")
text = text.replace(old_upload, new_upload, 1)

old_url = (
    '            return if (model == BambuModel.H2D) {\n'
    '                "ftp:///$name"\n'
    '            } else {\n'
    '                "file:///sdcard/cache/$name"\n'
    '            }\n'
)
new_url = (
    '            return when {\n'
    '                model == BambuModel.H2D || isASeries(model) -> "ftp:///$name"\n'
    '                else -> "file:///sdcard/cache/$name"\n'
    '            }\n'
)
if old_url not in text:
    raise SystemExit("projectFileUrl anchor missing")
text = text.replace(old_url, new_url, 1)

old_next = (
    '    private fun nextProjectSubmissionId(): String = projectSubmissionId.updateAndGet { current ->\n'
    '        if (current == Int.MAX_VALUE) 1 else current + 1\n'
    '    }.toString()\n'
)
new_next = (
    '    private fun nextProjectSubmissionId(): String = projectSubmissionId.updateAndGet { current ->\n'
    '        if (current >= 29_999) 20_000 else current + 1\n'
    '    }.toString()\n'
)
if old_next not in text:
    raise SystemExit("nextProjectSubmissionId anchor missing")
text = text.replace(old_next, new_next, 1)

old_timeout = (
    '                    "Printer allowed monitoring and upload but did not acknowledge the print request. " +\n'
    '                        "The uploaded 3MF was not started."\n'
)
new_timeout = (
    '                    "Printer allowed monitoring and upload but did not acknowledge the print request. " +\n'
    '                        "On current A1/A1 mini firmware this usually means command verification rejected the unsigned request " +\n'
    '                        "or Developer Mode is disabled. The uploaded 3MF was not started."\n'
)
if old_timeout in text:
    text = text.replace(old_timeout, new_timeout, 1)

client.write_text(text, encoding="utf-8")

gradle = root / "app/build.gradle"
g = gradle.read_text(encoding="utf-8")
g = re.sub(r'versionCode\s+\d+', 'versionCode 40103', g, count=1)
g = re.sub(r'versionName\s+"[^"]+"', 'versionName "4.0.1-a1.3"', g, count=1)
gradle.write_text(g, encoding="utf-8")

test = root / "app/src/test/java/com/u1/slicer/printer/A1CurrentFirmwarePrintPayloadTest.kt"
test.parent.mkdir(parents=True, exist_ok=True)
test.write_text("""package com.u1.slicer.printer

import com.u1.slicer.data.BambuModel
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class A1CurrentFirmwarePrintPayloadTest {
    @Test
    fun a1_uses_ftps_root_and_current_local_project_shape() {
        val name = "cube.gcode.3mf"
        assertEquals("/$name", DefaultBambuLanClient.projectUploadPath(BambuModel.A1, name))
        assertEquals("ftp:///$name", DefaultBambuLanClient.projectFileUrl(BambuModel.A1, name))

        val payload = DefaultBambuLanClient.projectFileCommandPayload(
            sequenceId = 20001,
            submissionId = "20001",
            remoteName = name,
            plateId = 1,
            amsMapping = listOf(0),
            useAms = true,
            subtaskName = "cube",
            model = BambuModel.A1,
            firmwareVersion = "01.07.02.00",
        )
        val print = JSONObject(payload).getJSONObject("print")
        assertEquals("20001", print.getString("sequence_id"))
        assertEquals("project_file", print.getString("command"))
        assertEquals("Metadata/plate_1.gcode", print.getString("param"))
        assertEquals("ftp:///$name", print.getString("url"))
        assertEquals("from_sd_card", print.getString("md5"))
        assertEquals("0", print.getString("project_id"))
        assertEquals("0", print.getString("subtask_id"))
        assertEquals("0", print.getString("task_id"))
        assertTrue(print.getJSONArray("ams_mapping").length() >= 1)
    }
}
""", encoding="utf-8")

print("A1 current-firmware print-start patch applied")
