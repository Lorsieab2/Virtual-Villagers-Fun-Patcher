/* New Believers' sites for island_timer_keep.h.  The timer is
   manager+0x17D3C.

   0x4426EA  cmp [ecx+0x17D3C], eax / ja 0x44285F      the trigger: due?
   0x4427CA  add [edi+0x17D3C], eax                     8-15 hours
   0x442801  add dword [eax+0x17D3C], 0x708             a first event's 30 minutes
   0x442834  add [edi+0x17D3C], eax                     8-15 hours
   0x7CCCFC  mov dword [edi+0x17D3C], 0                 the Origins Island Event: due now
   0x7CEE63  mov dword [eax+0x17D3C], 0                 the Origins Barrel of Babies: due now */

__declspec(naked) static void itk5_trigger(void) {
    __asm {
        cmp dword ptr [ecx + 0x17D3C], eax
        ja not_due
        pushad
        lea eax, [ecx + 0x17D3C]
        push eax
        call itk_firing
        add esp, 4
        popad
        push 0x4426F6
        ret
    not_due:
        pushad
        call itk_not_due
        popad
        push 0x44285F
        ret
    }
}

__declspec(naked) static void itk5_hours_a(void) {
    __asm {
        add dword ptr [edi + 0x17D3C], eax
        pushfd
        pushad
        lea eax, [edi + 0x17D3C]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x4427D0
        ret
    }
}

__declspec(naked) static void itk5_first(void) {
    __asm {
        add dword ptr [eax + 0x17D3C], 0x708
        pushfd
        pushad
        lea eax, [eax + 0x17D3C]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x44280B
        ret
    }
}

__declspec(naked) static void itk5_hours_b(void) {
    __asm {
        add dword ptr [edi + 0x17D3C], eax
        pushfd
        pushad
        lea eax, [edi + 0x17D3C]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x44283A
        ret
    }
}

__declspec(naked) static void itk5_bought(void) {
    __asm {
        pushfd
        pushad
        push 0
        lea eax, [edi + 0x17D3C]
        push eax
        call itk_note
        add esp, 8
        popad
        popfd
        mov dword ptr [edi + 0x17D3C], 0
        push 0x7CCD06
        ret
    }
}

__declspec(naked) static void itk5_barrel(void) {
    __asm {
        pushfd
        pushad
        push 0
        lea edx, [eax + 0x17D3C]
        push edx
        call itk_note
        add esp, 8
        popad
        popfd
        mov dword ptr [eax + 0x17D3C], 0
        push 0x7CEE6D
        ret
    }
}

static const itk_site ITK_VV5_SITES[] = {
    { 0x4426EAu, 12, { 0x39, 0x81, 0x3C, 0x7D, 0x01, 0x00, 0x0F, 0x87, 0x69, 0x01, 0x00, 0x00 }, (void *)itk5_trigger },
    { 0x4427CAu, 6, { 0x01, 0x87, 0x3C, 0x7D, 0x01, 0x00 }, (void *)itk5_hours_a },
    { 0x442801u, 10, { 0x81, 0x80, 0x3C, 0x7D, 0x01, 0x00, 0x08, 0x07, 0x00, 0x00 }, (void *)itk5_first },
    { 0x442834u, 6, { 0x01, 0x87, 0x3C, 0x7D, 0x01, 0x00 }, (void *)itk5_hours_b },
    { 0x7CCCFCu, 10, { 0xC7, 0x87, 0x3C, 0x7D, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00 }, (void *)itk5_bought },
    { 0x7CEE63u, 10, { 0xC7, 0x80, 0x3C, 0x7D, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00 }, (void *)itk5_barrel },
};
