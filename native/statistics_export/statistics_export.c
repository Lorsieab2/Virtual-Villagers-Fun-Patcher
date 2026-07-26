#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

enum {
    GAME_VV1 = 1,
    GAME_VV2 = 2,
    MAX_LONG_PATH = 32768
};

static int read_int(const unsigned char *manager, unsigned int offset) {
    return *(const int *)(manager + offset);
}

static int count_flags(
    const unsigned char *manager,
    const unsigned int *offsets,
    int count
) {
    int total = 0;
    int index;
    for (index = 0; index < count; ++index) {
        if (*(const unsigned char *)(manager + offsets[index]) != 0) {
            ++total;
        }
    }
    return total;
}

static int build_output_paths(
    int save_id,
    wchar_t *temporary,
    wchar_t *destination
) {
    wchar_t module_path[MAX_LONG_PATH];
    wchar_t *separator;
    DWORD length = GetModuleFileNameW(NULL, module_path, MAX_LONG_PATH);
    if (length == 0 || length >= MAX_LONG_PATH) {
        return 0;
    }
    separator = wcsrchr(module_path, L'\\');
    if (separator == NULL) {
        return 0;
    }
    *separator = L'\0';
    if (_snwprintf_s(
            temporary,
            MAX_LONG_PATH,
            _TRUNCATE,
            L"%ls\\Village Statistics - Save %d.tmp",
            module_path,
            save_id
        ) < 0) {
        return 0;
    }
    if (_snwprintf_s(
            destination,
            MAX_LONG_PATH,
            _TRUNCATE,
            L"%ls\\Village Statistics - Save %d.txt",
            module_path,
            save_id
        ) < 0) {
        return 0;
    }
    return 1;
}

static int real_hours(int game_id, const unsigned char *manager) {
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    typedef int (__fastcall *real_hours_function)(const void *, const void *);
    unsigned int rva;
    if (module == NULL) {
        return 0;
    }
    rva = game_id == GAME_VV1 ? 0x1D0E0u : 0x25A90u;
    return ((real_hours_function)(module + rva))(manager, NULL);
}

static int write_vv1(FILE *file, const unsigned char *manager) {
    static const unsigned int puzzle_offsets[16] = {
        0x9FA8, 0x9FB0, 0x9FB8, 0x9FC0,
        0x9FC8, 0x9FD8, 0x9FE0, 0x9FE8,
        0xA000, 0xA008, 0xA050, 0xA058,
        0xA080, 0xA088, 0xA090, 0xA098
    };
    return fprintf(
        file,
        "Virtual Villagers - A New Home\n"
        "Village Statistics\n\n"
        "Real Hours Played: %d\n"
        "Points Earned: %d\n"
        "Babies Made: %d\n"
        "Food Gathered: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Maximum Population: %d\n"
        "Villagers Buried: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        "Twins Birthed: %d\n"
        "Triplets Birthed: %d\n"
        "Puzzles Solved: %d of 16\n",
        real_hours(GAME_VV1, manager),
        read_int(manager, 0x9E20),
        read_int(manager, 0x9E24),
        read_int(manager, 0x9E28),
        read_int(manager, 0x9E2C),
        read_int(manager, 0x9E30),
        read_int(manager, 0x9E34),
        read_int(manager, 0x9E38),
        read_int(manager, 0x9E3C),
        read_int(manager, 0x9E40),
        read_int(manager, 0x9E44),
        read_int(manager, 0x9E48),
        count_flags(manager, puzzle_offsets, 16)
    ) >= 0;
}

static int write_vv2(FILE *file, const unsigned char *manager) {
    static const unsigned int puzzle_offsets[16] = {
        0x2E768, 0x2E770, 0x2E778, 0x2E780,
        0x2E788, 0x2E790, 0x2E798, 0x2E7A0,
        0x2E7A8, 0x2E7B0, 0x2E7B8, 0x2E7C0,
        0x2E7C8, 0x2E7D8, 0x2E7E0, 0x2E7E8
    };
    return fprintf(
        file,
        "Virtual Villagers - The Lost Children\n"
        "Village Statistics\n\n"
        "Real Hours Played: %d\n"
        "Points Earned: %d\n"
        "Babies Made: %d\n"
        "Food Gathered: %d\n"
        "People Cured: %d\n"
        "Mushrooms Found: %d\n"
        "Highest Population: %d\n"
        "Village Elders: %d\n"
        "Oldest Villager: %d\n"
        "Island Events Seen: %d\n"
        "Special Stews Found: %d\n"
        "Triplets Birthed: %d\n"
        "Puzzles Solved: %d of 16\n",
        real_hours(GAME_VV2, manager),
        read_int(manager, 0x2E4FC),
        read_int(manager, 0x2E500),
        read_int(manager, 0x2E504),
        read_int(manager, 0x2E508),
        read_int(manager, 0x2E50C),
        read_int(manager, 0x2E510),
        read_int(manager, 0x2E514),
        read_int(manager, 0x2E518),
        read_int(manager, 0x2E51C),
        read_int(manager, 0x2E520),
        read_int(manager, 0x2E524),
        count_flags(manager, puzzle_offsets, 16)
    ) >= 0;
}

__declspec(dllexport) int __stdcall WriteVillageStatistics(
    int game_id,
    const void *manager_pointer,
    int save_id
) {
    const unsigned char *manager = (const unsigned char *)manager_pointer;
    wchar_t temporary[MAX_LONG_PATH];
    wchar_t destination[MAX_LONG_PATH];
    FILE *file;
    int written;
    int closed;

    if (manager == NULL || save_id < 1 || save_id > 5) {
        return 0;
    }
    if (game_id != GAME_VV1 && game_id != GAME_VV2) {
        return 0;
    }
    if (!build_output_paths(save_id, temporary, destination)) {
        return 0;
    }

    file = _wfopen(temporary, L"wb");
    if (file == NULL) {
        return 0;
    }
    written = game_id == GAME_VV1
        ? write_vv1(file, manager)
        : write_vv2(file, manager);
    closed = fclose(file) == 0;
    if (!written || !closed) {
        DeleteFileW(temporary);
        return 0;
    }
    if (!MoveFileExW(
            temporary,
            destination,
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
        )) {
        DeleteFileW(temporary);
        return 0;
    }
    return 1;
}
