/* The Tree of Life's sites for island_timer_keep.h.  The timer is
   world+0x170E0.

   0x43FA3D  cmp [ecx+0x170E0], eax / ja 0x43FC0E      the trigger: due?
   0x43FB00  add [edi+0x170E0], eax                     8-15 hours
   0x43FB3E  add [edi+0x170E0], eax                     8-15 hours
   0x43FB9D  add dword [eax+0x170E0], 0x708             a first event's 30 minutes
   0x43FBD0  add [edi+0x170E0], eax                     8-15 hours
   0x4897B8  mov [ecx+0x170E0], eax                     the Origins Island Event: now + 5
   0x4897E6  mov dword [eax+0x170E0], 0                 the Origins Barrel of Babies: due now
   0x728A6B  mov [ecx+0x170E0], eax                     an Island Event a barrel went ahead of,
                                                        made due again: now + 5 */

__declspec(naked) static void itk4_trigger(void) {
    __asm {
        cmp dword ptr [ecx + 0x170E0], eax
        ja not_due
        pushad
        lea eax, [ecx + 0x170E0]
        push eax
        call itk_firing
        add esp, 4
        popad
        push 0x43FA49
        ret
    not_due:
        pushad
        call itk_not_due
        popad
        push 0x43FC0E
        ret
    }
}

__declspec(naked) static void itk4_hours_a(void) {
    __asm {
        add dword ptr [edi + 0x170E0], eax
        pushfd
        pushad
        lea eax, [edi + 0x170E0]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x43FB06
        ret
    }
}

__declspec(naked) static void itk4_hours_b(void) {
    __asm {
        add dword ptr [edi + 0x170E0], eax
        pushfd
        pushad
        lea eax, [edi + 0x170E0]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x43FB44
        ret
    }
}

__declspec(naked) static void itk4_first(void) {
    __asm {
        add dword ptr [eax + 0x170E0], 0x708
        pushfd
        pushad
        lea eax, [eax + 0x170E0]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x43FBA7
        ret
    }
}

__declspec(naked) static void itk4_hours_c(void) {
    __asm {
        add dword ptr [edi + 0x170E0], eax
        pushfd
        pushad
        lea eax, [edi + 0x170E0]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x43FBD6
        ret
    }
}

__declspec(naked) static void itk4_bought(void) {
    __asm {
        pushfd
        pushad
        push eax
        lea edx, [ecx + 0x170E0]
        push edx
        call itk_note
        add esp, 8
        popad
        popfd
        mov dword ptr [ecx + 0x170E0], eax
        push 0x4897BE
        ret
    }
}

__declspec(naked) static void itk4_barrel(void) {
    __asm {
        pushfd
        pushad
        push 0
        lea edx, [eax + 0x170E0]
        push edx
        call itk_note
        add esp, 8
        popad
        popfd
        mov dword ptr [eax + 0x170E0], 0
        push 0x4897F0
        ret
    }
}

__declspec(naked) static void itk4_again(void) {
    __asm {
        pushfd
        pushad
        push eax
        lea edx, [ecx + 0x170E0]
        push edx
        call itk_note
        add esp, 8
        popad
        popfd
        mov dword ptr [ecx + 0x170E0], eax
        push 0x728A71
        ret
    }
}

static const itk_site ITK_VV4_SITES[] = {
    { 0x43FA3Du, 12, { 0x39, 0x81, 0xE0, 0x70, 0x01, 0x00, 0x0F, 0x87, 0xC5, 0x01, 0x00, 0x00 }, (void *)itk4_trigger },
    { 0x43FB00u, 6, { 0x01, 0x87, 0xE0, 0x70, 0x01, 0x00 }, (void *)itk4_hours_a },
    { 0x43FB3Eu, 6, { 0x01, 0x87, 0xE0, 0x70, 0x01, 0x00 }, (void *)itk4_hours_b },
    { 0x43FB9Du, 10, { 0x81, 0x80, 0xE0, 0x70, 0x01, 0x00, 0x08, 0x07, 0x00, 0x00 }, (void *)itk4_first },
    { 0x43FBD0u, 6, { 0x01, 0x87, 0xE0, 0x70, 0x01, 0x00 }, (void *)itk4_hours_c },
    { 0x4897B8u, 6, { 0x89, 0x81, 0xE0, 0x70, 0x01, 0x00 }, (void *)itk4_bought },
    { 0x4897E6u, 10, { 0xC7, 0x80, 0xE0, 0x70, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00 }, (void *)itk4_barrel },
    { 0x728A6Bu, 6, { 0x89, 0x81, 0xE0, 0x70, 0x01, 0x00 }, (void *)itk4_again },
};
