#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: seed_room1_depth_matte.py /path/to/agile-gdx")

root = Path(sys.argv[1]).resolve()
editor = root / "core/src/main/java/com/agifans/agile/SceneMaskEditor.java"
text = editor.read_text()

# Room 1 matte generated from the user-approved AI tree silhouette, then reduced
# to AGI's 160x168 mask plane. Each row is y:x0-x1,x2-x3,...
ROOM1_OCCLUDER_RUNS = '1:129-130,142;2:128-131,133,141-144;3:109-110,115,128-134,137,141-146;4:106,108-110,113-115,121-122,127-134,137-138,140-147;5:105-110,113-118,120-123,127-134,137-147;6:105-110,112-115,117-124,127-146;7:105-123,127-146,150;8:105-146,148-150;9:103-152;10:103-151;11:103-151;12:103-150;13:103-151;14:102,104-152;15:100,102-152;16:100-152,154;17:100-155;18:100-151,153-155;19:99-155;20:101-155;21:101,104-156;22:103-155;23:102-155;24:101-155;25:100-154;26:100-155;27:100-155;28:99-156;29:99-157;30:100-158;31:100-159;32:102-105,107-159;33:102-103,105-158;34:102,105-159;35:105-159;36:104-159;37:103,105-159;38:102-159;39:101-159;40:102-159;41:101-159;42:100-157;43:101-157;44:102-107,109-157;45:102-107,109-158;46:102,104-105,109-158;47:109-152,154-159;48:105-106,108-159;49:105-159;50:105-136,138-143,145-159;51:104-143,145-159;52:104-159;53:103-159;54:103-159;55:103-159;56:102-144,146-159;57:103-144,146-159;58:101-144,146-159;59:101-159;60:100-125,128-158;61:103-105,107-125,127-158;62:102-105,107-109,111-125,128-159;63:102-105,108-125,129-159;64:102,104,108-120,122-125,130-138,140-159;65:108-120,123-125,130-138,140-159;66:107-125,130-133,135-137,139-159;67:107-125,130-133,135-137,139-151,153-159;68:107-118,120-124,130-133,135-136,138-159;69:107-118,120-124,130-133,135-136,138-159;70:106-119,121-124,130-133,135-150,152-159;71:106-119,121-124,130-133,135-149,151-159;72:106-124,130-133,135-159;73:106-124,130-133,135,137-159;74:106-112,114-124,130-133,135,137-158;75:108-112,114-124,130-133,138-142,144-158;76:108-112,114-124,130-133,138-142,145-157;77:108-112,114-124,130-133,138-142,145-158;78:108-111,118-124,129-134,138-142,145-150,152-158;79:109,111,118-124,128-134,138-142,144-157;80:118-124,128-134,138-158;81:115-117,120-125,128-134,138-158;82:115-118,120-125,128-133,137-158;83:115-125,129-133,137-158;84:114-125,129-133,137-157;85:114-125,130-133,137-158;86:113-116,118-125,130-133,137-150,152-158;87:113,115-116,118-125,130-133,137-150,152-158;88:113,115-116,118-126,130-134,137-150,153-158;89:115-116,121-126,130-134,137-151,153-158;90:122-127,130-134,136-150,153-157;91:122-127,130-134,136-151,155-157;92:123-127,130-134,136-151;93:123-128,130-134,136-150;94:123-128,131-143,146-151;95:123-128,131-141,143,145-148,150-151;96:124-129,131-141,145-148;97:124-129,131-141,145-148;98:124-129,131-141,147-148;99:124-141;100:125-140;101:125-140;102:125-140;103:125-140;104:126-140;105:126-140;106:126-139;107:127-139;108:127-139;109:128-139;110:128-139;111:128-139;112:128-139;113:129-138;114:129-138;115:129-138;116:130-138;117:130-138;118:130-138;119:130-139;120:130-139;121:130-139;122:130-139;123:130-139;124:130-139;125:130-139;126:130-139;127:130-139;128:130-139;129:130-139;130:130-139;131:130-139;132:130-139;133:130-139;134:130-139;135:130-140;136:130-140;137:130-140;138:130-140;139:130-140;140:130-140;141:130-141;142:130-141;143:130-141;144:130-141;145:130-142;146:129-142;147:129-142;148:129-143;149:128-143;150:130-142;151:130-142;152:135-139'
ROOM1_BEHIND_RUNS = '110:132-141;111:129-144;112:127-145;113:125-147;114:124-148;115:123-149;116:122-150;117:121-151;118:121-152;119:120-153;120:119-153;121:119-154;122:118-154;123:118-155;124:118-155;125:117-155;126:117-155;127:117-156;128:117-156;129:117-156;130:117-156;131:117-156;132:117-156;133:117-156;134:117-156;135:117-156;136:117-155;137:117-155;138:118-155;139:118-154;140:118-154;141:119-154;142:119-153;143:120-152;144:121-135,138-152;145:122-131,141-151;146:122-130,143-150;147:123-129,143-149;148:125-129,144-148;149:125-128,144-147;150:126-128,144-146;151:127-128,144-145'
ROOM1_COLLISION_RUNS = '144:134-139;145:132-141;146:130-142;147:130-143;148:129-143;149:129-144;150:129-144;151:129-144;152:129-144;153:129-143;154:130-142;155:131-141;156:133-140'

anchor = """    private static final int BEHIND = 2;\n"""
constants = """    private static final int BEHIND = 2;
    private static final String ROOM1_OCCLUDER_RUNS = \"__OCCLUDER__\";
    private static final String ROOM1_COLLISION_RUNS = \"__COLLISION__\";
    private static final String ROOM1_BEHIND_RUNS = \"__BEHIND__\";
"""
constants = constants.replace("__OCCLUDER__", ROOM1_OCCLUDER_RUNS)
constants = constants.replace("__COLLISION__", ROOM1_COLLISION_RUNS)
constants = constants.replace("__BEHIND__", ROOM1_BEHIND_RUNS)
if text.count(anchor) != 1:
    raise RuntimeError("SceneMaskEditor layer constants anchor not found")
text = text.replace(anchor, constants)

# New preference namespace ensures stale hand-painted experiments do not hide
# this built-in seed. Any edits made after this build persist normally.
old_prefs = 'this.prefs = Gdx.app.getPreferences("agi-scene-mask-editor-v1");'
new_prefs = 'this.prefs = Gdx.app.getPreferences("agi-scene-mask-editor-v2");'
if text.count(old_prefs) != 1:
    raise RuntimeError("SceneMaskEditor preferences namespace not found")
text = text.replace(old_prefs, new_prefs)

decode_anchor = """    private void decode(String text, boolean[][] mask) {
"""
run_decoder = """    private void decodeRuns(String runs, boolean[][] mask) {
        if (runs == null || runs.length() == 0) return;
        String[] rows = runs.split(";");
        for (String row : rows) {
            int colon = row.indexOf(':');
            if (colon <= 0) continue;
            int y = Integer.parseInt(row.substring(0, colon));
            if (y < 0 || y >= HEIGHT) continue;
            String[] spans = row.substring(colon + 1).split(",");
            for (String span : spans) {
                int dash = span.indexOf('-');
                int start;
                int end;
                if (dash < 0) {
                    start = Integer.parseInt(span);
                    end = start;
                } else {
                    start = Integer.parseInt(span.substring(0, dash));
                    end = Integer.parseInt(span.substring(dash + 1));
                }
                start = Math.max(0, start);
                end = Math.min(WIDTH - 1, end);
                for (int x = start; x <= end; x++) mask[y][x] = true;
            }
        }
    }

    private void decode(String text, boolean[][] mask) {
"""
if text.count(decode_anchor) != 1:
    raise RuntimeError("SceneMaskEditor decode method anchor not found")
text = text.replace(decode_anchor, run_decoder)

load_old = """        decode(prefs.getString(key("occluder"), ""), masks[OCCLUDER]);
        decode(prefs.getString(key("collision"), ""), masks[COLLISION]);
        decode(prefs.getString(key("behind"), ""), masks[BEHIND]);
        boolean active = prefs.getBoolean(key("active"), false);
"""
load_new = """        String savedOccluder = prefs.getString(key("occluder"), "");
        String savedCollision = prefs.getString(key("collision"), "");
        String savedBehind = prefs.getString(key("behind"), "");
        boolean hasSavedMask = savedOccluder.length() == HEIGHT * 40
                || savedCollision.length() == HEIGHT * 40
                || savedBehind.length() == HEIGHT * 40;
        boolean active;
        if (room == 1 && !hasSavedMask) {
            decodeRuns(ROOM1_OCCLUDER_RUNS, masks[OCCLUDER]);
            decodeRuns(ROOM1_COLLISION_RUNS, masks[COLLISION]);
            decodeRuns(ROOM1_BEHIND_RUNS, masks[BEHIND]);
            active = true;
            dirty = true;
        } else {
            decode(savedOccluder, masks[OCCLUDER]);
            decode(savedCollision, masks[COLLISION]);
            decode(savedBehind, masks[BEHIND]);
            active = prefs.getBoolean(key("active"), false);
        }
"""
if text.count(load_old) != 1:
    raise RuntimeError("SceneMaskEditor saved-mask load block not found")
text = text.replace(load_old, load_new)

editor.write_text(text)
print("Room 1 AI depth matte seeded into SceneMaskEditor")