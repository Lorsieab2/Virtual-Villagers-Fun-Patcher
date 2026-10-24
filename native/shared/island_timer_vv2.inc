/* The Lost Children's sites for island_timer_keep.h.  The timer is
   world+0x2EAE0.

   0x42EECD  cmp [edi+0x2EAE0], eax / ja 0x42F1D4      the trigger: due?
   0x42EFA1  mov [edi+0x2EAE0], ebp                     the sack / vial's 10-19 hours
   0x42F02A  mov [ebp+0x2EAE0], ecx                     the single-result events' 10-19 hours
                                                        (the flags of 0x42F028 are live)
   0x42F147  add dword [eax+0x2EAE0], 0x708             a first event's 30 minutes
   0x42F17F  mov [edi+0x2EAE0], ecx                     the two-choice events' 10-19 hours
   0x494824  mov [edi+0x2EAE0], eax                     the Origins Island Event: now + 5 */

__declspec(naked) static void itk2_trigger(void) {
    __asm {
        cmp dword ptr [edi + 0x2EAE0], eax
        ja not_due
        pushad
        lea eax, [edi + 0x2EAE0]
        push eax
        call itk_firing
        add esp, 4
        popad
        push 0x42EED9
        ret
    not_due:
        pushad
        call itk_not_due
        popad
        push 0x42F1D4
        ret
    }
}

__declspec(naked) static void itk2_sack(void) {
    __asm {
        mov dword ptr [edi + 0x2EAE0], ebp
        pushfd
        pushad
        lea eax, [edi + 0x2EAE0]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x42EFA7
        ret
    }
}

__declspec(naked) static void itk2_single(void) {
    __asm {
        mov dword ptr [ebp + 0x2EAE0], ecx
        pushfd
        pushad
        lea eax, [ebp + 0x2EAE0]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x42F030
        ret
    }
}

__declspec(naked) static void itk2_first(void) {
    __asm {
        add dword ptr [eax + 0x2EAE0], 0x708
        pushfd
        pushad
        lea eax, [eax + 0x2EAE0]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x42F151
        ret
    }
}

__declspec(naked) static void itk2_two_choice(void) {
    __asm {
        mov dword ptr [edi + 0x2EAE0], ecx
        pushfd
        pushad
        lea eax, [edi + 0x2EAE0]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x42F185
        ret
    }
}

__declspec(naked) static void itk2_bought(void) {
    __asm {
        pushfd
        pushad
        push eax
        lea ecx, [edi + 0x2EAE0]
        push ecx
        call itk_note
        add esp, 8
        popad
        popfd
        mov dword ptr [edi + 0x2EAE0], eax
        push 0x49482A
        ret
    }
}

static const itk_site ITK_VV2_SITES[] = {
    { 0x42EECDu, 12, { 0x39, 0x87, 0xE0, 0xEA, 0x02, 0x00, 0x0F, 0x87, 0xFB, 0x02, 0x00, 0x00 }, (void *)itk2_trigger },
    { 0x42EFA1u, 6, { 0x89, 0xAF, 0xE0, 0xEA, 0x02, 0x00 }, (void *)itk2_sack },
    { 0x42F02Au, 6, { 0x89, 0x8D, 0xE0, 0xEA, 0x02, 0x00 }, (void *)itk2_single },
    { 0x42F147u, 10, { 0x81, 0x80, 0xE0, 0xEA, 0x02, 0x00, 0x08, 0x07, 0x00, 0x00 }, (void *)itk2_first },
    { 0x42F17Fu, 6, { 0x89, 0x8F, 0xE0, 0xEA, 0x02, 0x00 }, (void *)itk2_two_choice },
    { 0x494824u, 6, { 0x89, 0x87, 0xE0, 0xEA, 0x02, 0x00 }, (void *)itk2_bought },
};
