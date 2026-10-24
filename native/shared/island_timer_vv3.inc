/* The Secret City's sites for island_timer_keep.h.  The timer is
   manager+0x12EF4.

   0x468732  cmp [ecx+0x12EF4], eax / ja 0x4688DF      the trigger: due?
   0x468809  mov [edi+0x12EF4], ebp                     8-15 hours
   0x468842  mov [edi+0x12EF4], ecx                     8-15 hours (the flags of 0x468840 are live)
   0x468899  add dword [eax+0x12EF4], 0x708             a first event's 30 minutes
   0x4688D4  mov [edi+0x12EF4], ecx                     8-15 hours
   0x6DF34A  mov [ecx+0x12EF4], eax                     the Origins Island Event's helper
                                                        (and the Story / Cheat Upgrades'
                                                        arms, which call it): now + 5

   The Origins Barrel of Babies is presented by its own call of the event
   selector (0x47B423) and never writes the timer, so it is not here. */

__declspec(naked) static void itk3_trigger(void) {
    __asm {
        cmp dword ptr [ecx + 0x12EF4], eax
        ja not_due
        pushad
        lea eax, [ecx + 0x12EF4]
        push eax
        call itk_firing
        add esp, 4
        popad
        push 0x46873E
        ret
    not_due:
        pushad
        call itk_not_due
        popad
        push 0x4688DF
        ret
    }
}

__declspec(naked) static void itk3_hours_a(void) {
    __asm {
        mov dword ptr [edi + 0x12EF4], ebp
        pushfd
        pushad
        lea eax, [edi + 0x12EF4]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x46880F
        ret
    }
}

__declspec(naked) static void itk3_hours_b(void) {
    __asm {
        mov dword ptr [edi + 0x12EF4], ecx
        pushfd
        pushad
        lea eax, [edi + 0x12EF4]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x468848
        ret
    }
}

__declspec(naked) static void itk3_first(void) {
    __asm {
        add dword ptr [eax + 0x12EF4], 0x708
        pushfd
        pushad
        lea eax, [eax + 0x12EF4]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x4688A3
        ret
    }
}

__declspec(naked) static void itk3_hours_c(void) {
    __asm {
        mov dword ptr [edi + 0x12EF4], ecx
        pushfd
        pushad
        lea eax, [edi + 0x12EF4]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x4688DA
        ret
    }
}

__declspec(naked) static void itk3_bought(void) {
    __asm {
        pushfd
        pushad
        push eax
        lea edx, [ecx + 0x12EF4]
        push edx
        call itk_note
        add esp, 8
        popad
        popfd
        mov dword ptr [ecx + 0x12EF4], eax
        push 0x6DF350
        ret
    }
}

static const itk_site ITK_VV3_SITES[] = {
    { 0x468732u, 12, { 0x39, 0x81, 0xF4, 0x2E, 0x01, 0x00, 0x0F, 0x87, 0xA1, 0x01, 0x00, 0x00 }, (void *)itk3_trigger },
    { 0x468809u, 6, { 0x89, 0xAF, 0xF4, 0x2E, 0x01, 0x00 }, (void *)itk3_hours_a },
    { 0x468842u, 6, { 0x89, 0x8F, 0xF4, 0x2E, 0x01, 0x00 }, (void *)itk3_hours_b },
    { 0x468899u, 10, { 0x81, 0x80, 0xF4, 0x2E, 0x01, 0x00, 0x08, 0x07, 0x00, 0x00 }, (void *)itk3_first },
    { 0x4688D4u, 6, { 0x89, 0x8F, 0xF4, 0x2E, 0x01, 0x00 }, (void *)itk3_hours_c },
    { 0x6DF34Au, 6, { 0x89, 0x81, 0xF4, 0x2E, 0x01, 0x00 }, (void *)itk3_bought },
};
