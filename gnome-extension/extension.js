/* Desktop Todo window layer helper (GNOME Shell 42).
 *
 * Wayland 下普通客户端不能自行改变窗口层级；扩展运行在 Shell 进程内，
 * 由 D-Bus 接收应用的层级设置，并对匹配的窗口执行 make_above/lower。
 * 只监听窗口创建/销毁和设置变化，不运行定时轮询。
 */
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;

const DBUS_NAME = 'com.sunmaple.desktodo';
const DBUS_PATH = '/com/sunmaple/desktodo/layer';
const IFACE = 'com.sunmaple.desktodo.Layer';
const WINDOW_TITLE = '桌面待办';

const INTERFACE_XML = `
<node>
  <interface name="com.sunmaple.desktodo.Layer">
    <method name="SetMode">
      <arg type="s" name="mode" direction="in"/>
      <arg type="b" name="ok" direction="out"/>
    </method>
    <method name="GetMode">
      <arg type="s" name="mode" direction="out"/>
    </method>
    <method name="Ping">
      <arg type="s" name="reply" direction="out"/>
    </method>
  </interface>
</node>`;

let state = null;

function findTodoWindows() {
    // Shell 42 的 global.get_window_actors() 返回 actor 列表。
    const actors = global.get_window_actors();
    const result = [];
    for (const actor of actors) {
        try {
            const win = actor.get_meta_window();
            if (!win)
                continue;
            const title = win.get_title() || '';
            const wmClass = win.get_wm_class() || '';
            // 标题是应用自己的稳定标识；wm_class 作为 X11/兼容场景补充。
            if (title === WINDOW_TITLE || wmClass === 'desktoptodo' ||
                wmClass === 'com.sunmaple.desktodo')
                result.push(win);
        } catch (e) {
            logError(e, 'DesktopTodo layer: window inspection failed');
        }
    }
    return result;
}

function applyToWindow(win, mode) {
    if (!win)
        return;
    try {
        // 先清理旧状态，再设置新状态，避免 above/below 残留。
        if (win.is_above && win.is_above())
            win.unmake_above();
        if (mode === 'top') {
            win.make_above();
        } else if (mode === 'bottom') {
            if (win.is_above && win.is_above())
                win.unmake_above();
            win.lower();
        }
    } catch (e) {
        logError(e, 'DesktopTodo layer: applying window mode failed');
    }
}

function applyAll() {
    if (!state)
        return;
    for (const win of findTodoWindows())
        applyToWindow(win, state.mode);
}

function SetMode(mode) {
    if (mode !== 'normal' && mode !== 'top' && mode !== 'bottom')
        return false;
    if (!state)
        return false;
    state.mode = mode;
    applyAll();
    return true;
}

function GetMode() {
    return state ? state.mode : 'normal';
}

function Ping() {
    return 'desktoptodo-layer';
}

function enable() {
    state = {
        mode: 'normal',
        ownerId: 0,
        object: null,
        windowCreatedId: 0,
    };

    // 只有应用窗口被创建时才重新应用层级，不轮询。
    state.windowCreatedId = global.display.connect('window-created', (_display, win) => {
        if (!state)
            return;
        const title = win.get_title() || '';
        const wmClass = win.get_wm_class() || '';
        if (title === WINDOW_TITLE || wmClass === 'desktoptodo' ||
            wmClass === 'com.sunmaple.desktodo') {
            // 等窗口 map 完成后再操作，避免过早调用被合成器覆盖。
            GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
                if (state)
                    applyToWindow(win, state.mode);
                return GLib.SOURCE_REMOVE;
            });
        }
    });

    state.object = Gio.DBusExportedObject.wrapJSObject(INTERFACE_XML, {
        SetMode,
        GetMode,
        Ping,
    });
    state.object.export(Gio.DBus.session, DBUS_PATH);

    state.ownerId = Gio.bus_own_name(
        Gio.BusType.SESSION,
        DBUS_NAME,
        Gio.BusNameOwnerFlags.NONE,
        null,
        () => applyAll(),
        () => {}
    );
}

function disable() {
    if (!state)
        return;
    if (state.windowCreatedId) {
        global.display.disconnect(state.windowCreatedId);
        state.windowCreatedId = 0;
    }
    if (state.object) {
        state.object.flush();
        state.object.unexport();
        state.object = null;
    }
    if (state.ownerId) {
        Gio.bus_unown_name(state.ownerId);
        state.ownerId = 0;
    }
    // 关闭扩展时恢复普通层级，避免把窗口永久留在 above 状态。
    for (const win of findTodoWindows())
        applyToWindow(win, 'normal');
    state = null;
}
