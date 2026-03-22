/*
 * hook.js — Frida Hook Script (Frida 16.5.9)
 */

"use strict";

var _seq = 0;
function nextId() { return "EVT" + (++_seq); }

function safeWide(ptr) {
    try { return ptr.isNull() ? "" : ptr.readUtf16String() || ""; }
    catch (_) { return ""; }
}
function safeAnsi(ptr) {
    try { return ptr.isNull() ? "" : ptr.readAnsiString() || ""; }
    catch (_) { return ""; }
}
function handleToPath(handle) {
    try {
        var fn = new NativeFunction(
            Module.getExportByName("kernel32.dll", "GetFinalPathNameByHandleW"),
            "uint32", ["pointer", "pointer", "uint32", "uint32"]
        );
        var buf = Memory.alloc(2048);
        if (fn(handle, buf, 1024, 0) > 0) return buf.readUtf16String();
    } catch (_) {}
    return "";
}

// ── Filter: return true = skip this event entirely ────────────────────────────
function shouldSkip(path, isWrite) {
    if (!path || path.length < 3) return true;
    var up = path.toUpperCase();

    // Always pass through SCADA paths — never skip
    if (up.indexOf("SCADA") !== -1) return false;

    // Always pass through our sim_write target — never skip
    if (up.indexOf("SIM_WRITE") !== -1) return false;

    // Skip Windows/Python internals
    if (up.indexOf("_MEI")        !== -1) return true;
    if (up.indexOf(".DLL")        !== -1) return true;
    if (up.indexOf(".PYD")        !== -1) return true;
    if (up.indexOf(".PYZ")        !== -1) return true;
    if (up.indexOf(".PYC")        !== -1) return true;
    if (up.indexOf("\\WINDOWS\\") !== -1) return true;
    if (up.indexOf("SYSTEM32")    !== -1) return true;
    if (up.indexOf("\\PYTHON313") !== -1) return true;
    if (up.indexOf("APPDATA\\LOCAL\\PROGRAMS\\PYTHON") !== -1) return true;

    // Skip random unnamed Temp files (Python internal temp — short random names)
    // Only intercept Temp writes if path contains "sim_write" (already handled above)
    if (up.indexOf("\\TEMP\\") !== -1 && up.indexOf("SIM_WRITE") === -1) return true;

    // Skip everything else that is not SCADA/sim_write
    return true;
}

function waitForPython(event_id) {
    const op = recv(event_id, function(_) {});
    op.wait();
}

function fireEvent(hook, path, bytes, isWrite) {
    if (shouldSkip(path, isWrite)) return;
    var eid = nextId();
    send({ hook: hook, event_id: eid, path: path, bytes: bytes, is_write: isWrite });
    waitForPython(eid);
}


// ── CreateFileW ───────────────────────────────────────────────────────────────
var cfwAddr = Module.findExportByName("kernel32.dll", "CreateFileW");
if (cfwAddr) {
    Interceptor.attach(cfwAddr, {
        onEnter: function(args) {
            var path    = safeWide(args[0]);
            var isWrite = (args[1].toInt32() & 0x40000000) !== 0;
            fireEvent("CreateFileW", path, 0, isWrite);
        }
    });
    console.log("[hook.js] CreateFileW hooked OK");
}

// ── CreateFileA ───────────────────────────────────────────────────────────────
var cfaAddr = Module.findExportByName("kernel32.dll", "CreateFileA");
if (cfaAddr) {
    Interceptor.attach(cfaAddr, {
        onEnter: function(args) {
            var path    = safeAnsi(args[0]);
            var isWrite = (args[1].toInt32() & 0x40000000) !== 0;
            fireEvent("CreateFileA", path, 0, isWrite);
        }
    });
    console.log("[hook.js] CreateFileA hooked OK");
}

// ── NtCreateFile ──────────────────────────────────────────────────────────────
var ntcfAddr = Module.findExportByName("ntdll.dll", "NtCreateFile");
if (ntcfAddr) {
    Interceptor.attach(ntcfAddr, {
        onEnter: function(args) {
            try {
                var access  = args[1].toInt32();
                var isWrite = (access & 0x40100000) !== 0;
                var ustrPtr = args[2].add(8).readPointer();
                var bufPtr  = ustrPtr.add(4).readPointer();
                var path    = bufPtr.readUtf16String();
                if (path) path = path.replace(/^\\\?\?\\/, "").replace(/^\\Device\\[^\\]+/, "");
                fireEvent("NtCreateFile", path, 0, isWrite);
            } catch(_) {}
        }
    });
    console.log("[hook.js] NtCreateFile hooked OK");
}

// ── WriteFile ─────────────────────────────────────────────────────────────────
var wfAddr = Module.findExportByName("kernel32.dll", "WriteFile");
if (wfAddr) {
    Interceptor.attach(wfAddr, {
        onEnter: function(args) {
            var handle = args[0];
            var bytes  = args[2].toInt32();
            var hval   = handle.toInt32();
            if (hval === 1 || hval === 2 ||
                hval === -10 || hval === -11 || hval === -12) return;
            if (bytes <= 0) return;
            var path = handleToPath(handle);
            fireEvent("WriteFile", path, bytes, true);
        }
    });
    console.log("[hook.js] WriteFile hooked OK");
}

// ── NtWriteFile ───────────────────────────────────────────────────────────────
var ntwfAddr = Module.findExportByName("ntdll.dll", "NtWriteFile");
if (ntwfAddr) {
    Interceptor.attach(ntwfAddr, {
        onEnter: function(args) {
            try {
                var handle = args[0];
                var bytes  = args[6].toInt32();
                if (bytes <= 0) return;
                var path = handleToPath(handle);
                fireEvent("NtWriteFile", path, bytes, true);
            } catch(_) {}
        }
    });
    console.log("[hook.js] NtWriteFile hooked OK");
}

console.log("[hook.js] All hooks active.");
