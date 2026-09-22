from pathlib import Path
import re

root = Path("src")

client = root / "app/src/main/java/com/u1/slicer/printer/BambuLanClient.kt"
s = client.read_text(encoding="utf-8")
old = '''            return when {
                model == BambuModel.H2D || isASeries(model) -> "/$name"
                else -> "/cache/$name"
            }
'''
new = '''            return when {
                isASeries(model) -> "/model/$name"
                model == BambuModel.H2D -> "/$name"
                else -> "/cache/$name"
            }
'''
if old not in s:
    raise SystemExit("A-series upload path anchor missing")
s = s.replace(old, new, 1)
client.write_text(s, encoding="utf-8")

vm = root / "app/src/main/java/com/u1/slicer/printer/PrinterViewModel.kt"
s = vm.read_text(encoding="utf-8")
old_call = '''                val result = printerRepo.uploadAndPrintBambuProject(
                    projectFile = projectFile,
                    remoteName = filename,
                    plateId = plateId,
                    amsMapping = amsMapping,
                    useAms = useAms,
                )
                if (!isCurrentPrinterAction(actionContext)) return@launch
                _sendingState.value = when (result) {
                    TransportCommandResult.Success -> SendingState.PrintStarted
                    is TransportCommandResult.Unsupported -> SendingState.Error(result.reason)
                    is TransportCommandResult.Failure -> SendingState.Error(result.reason)
                }
'''
new_call = '''                // A1 Pocket a1.4: upload to /model and let Bambu Handy perform
                // the final authorized start. This keeps cloud/Handy enabled.
                val result = printerRepo.uploadOnlyBambuProject(projectFile, filename)
                if (!isCurrentPrinterAction(actionContext)) return@launch
                _sendingState.value = when (result) {
                    TransportCommandResult.Success -> SendingState.UploadComplete
                    is TransportCommandResult.Unsupported -> SendingState.Error(result.reason)
                    is TransportCommandResult.Failure -> SendingState.Error(result.reason)
                }
                if (result is TransportCommandResult.Success) {
                    com.u1.slicer.AppEventNotifier.notify(
                        getApplication(),
                        com.u1.slicer.AppEventNotifier.Event.UploadComplete(filename)
                    )
                    withContext(Dispatchers.Main) {
                        launchBambuHandy(filename)
                    }
                }
'''
if old_call not in s:
    raise SystemExit("sendBambuProjectAndPrint call anchor missing")
s = s.replace(old_call, new_call, 1)

insert_anchor = '''    fun sendBambuProjectUploadOnly(projectFile: File, modelName: String? = null) {
'''
helper = '''    private fun launchBambuHandy(filename: String) {
        val ctx = getApplication<Application>()
        val packageName = "bbl.intl.bambulab.com"
        val launch = ctx.packageManager.getLaunchIntentForPackage(packageName)
        if (launch != null) {
            android.widget.Toast.makeText(
                ctx,
                "Uploaded to printer Models: $filename",
                android.widget.Toast.LENGTH_LONG,
            ).show()
            launch.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
            ctx.startActivity(launch)
            return
        }

        val market = android.content.Intent(
            android.content.Intent.ACTION_VIEW,
            android.net.Uri.parse("market://details?id=$packageName"),
        ).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        val web = android.content.Intent(
            android.content.Intent.ACTION_VIEW,
            android.net.Uri.parse("https://play.google.com/store/apps/details?id=$packageName"),
        ).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { ctx.startActivity(market) }
            .onFailure { ctx.startActivity(web) }
    }

'''
if insert_anchor not in s:
    raise SystemExit("VM helper insertion anchor missing")
s = s.replace(insert_anchor, helper + insert_anchor, 1)
vm.write_text(s, encoding="utf-8")

manifest = root / "app/src/main/AndroidManifest.xml"
s = manifest.read_text(encoding="utf-8")
if 'bbl.intl.bambulab.com' not in s:
    app_anchor = '    <application'
    if app_anchor not in s:
        raise SystemExit("manifest application anchor missing")
    s = s.replace(
        app_anchor,
        '''    <queries>
        <package android:name="bbl.intl.bambulab.com" />
    </queries>

    <application''',
        1,
    )
manifest.write_text(s, encoding="utf-8")

main = root / "app/src/main/java/com/u1/slicer/MainActivity.kt"
s = main.read_text(encoding="utf-8")
s = s.replace(
    '"This uploads the ready-to-print 3MF and starts plate ${pending.project.selectedPlateId} on the printer."',
    '"Uploads the ready-to-print 3MF to the printer Models library, then opens Bambu Handy for the authorized final start."',
)
s = s.replace('"Upload & Start Print"', '"Upload & Open Handy"')
main.write_text(s, encoding="utf-8")

screen = root / "app/src/main/java/com/u1/slicer/ui/PrinterScreen.kt"
s = screen.read_text(encoding="utf-8")
s = s.replace(
    '"Open the project from the printer screen if you want to start it later."',
    '"The project is in the printer Models library. Open Bambu Handy to start it securely."',
)
screen.write_text(s, encoding="utf-8")

gradle = root / "app/build.gradle"
g = gradle.read_text(encoding="utf-8")
g = re.sub(r'versionCode\s+\d+', 'versionCode 40104', g, count=1)
g = re.sub(r'versionName\s+"[^"]+"', 'versionName "4.0.1-a1.4"', g, count=1)
gradle.write_text(g, encoding="utf-8")

test = root / "app/src/test/java/com/u1/slicer/printer/A1HandyBridgeTest.kt"
test.parent.mkdir(parents=True, exist_ok=True)
test.write_text("""package com.u1.slicer.printer

import com.u1.slicer.data.BambuModel
import org.junit.Assert.assertEquals
import org.junit.Test

class A1HandyBridgeTest {
    @Test
    fun a1_projects_upload_to_user_visible_model_library() {
        assertEquals(
            "/model/cube.gcode.3mf",
            DefaultBambuLanClient.projectUploadPath(BambuModel.A1, "cube.gcode.3mf"),
        )
        assertEquals(
            "/model/cube.gcode.3mf",
            DefaultBambuLanClient.projectUploadPath(BambuModel.A1_MINI, "cube.gcode.3mf"),
        )
    }
}
""", encoding="utf-8")

print("A1 Handy bridge patch applied")
