/* A New Home's sites for island_timer_keep.h.  The timer is world+0xA300.

   0x4237BD  cmp [edi+0xA300], eax / ja 0x423ABE      the trigger: due?
   0x423891  mov [edi+0xA300], ebp                     the crate's 12-23 hours
   0x42391A  mov [ebp+0xA300], ecx                     the island events' 12-23 hours
                                                       (the flags of 0x423918 are live)
   0x423A37  add dword [eax+0xA300], 0x708             a first event's 30 minutes
   0x423A6F  mov [edi+0xA300], ecx                     the visitors' 12-23 hours
   0x456B47  mov [edi+0xA300], eax                     the Origins Island Event: now + 5

   Each write is made exactly as before; the stub then tells the keeper. */

__declspec(naked) static void itk1_trigger(void) {
    __asm {
        cmp dword ptr [edi + 0xA300], eax
        ja not_due
        pushad
        lea eax, [edi + 0xA300]
        push eax
        call itk_firing
        add esp, 4
        popad
        push 0x4237C9
        ret
    not_due:
        pushad
        call itk_not_due
        popad
        push 0x423ABE
        ret
    }
}

__declspec(naked) static void itk1_crate(void) {
    __asm {
        mov dword ptr [edi + 0xA300], ebp
        pushfd
        pushad
        lea eax, [edi + 0xA300]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x423897
        ret
    }
}

__declspec(naked) static void itk1_island(void) {
    __asm {
        mov dword ptr [ebp + 0xA300], ecx
        pushfd
        pushad
        lea eax, [ebp + 0xA300]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x423920
        ret
    }
}

__declspec(naked) static void itk1_first(void) {
    __asm {
        add dword ptr [eax + 0xA300], 0x708
        pushfd
        pushad
        lea eax, [eax + 0xA300]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x423A41
        ret
    }
}

__declspec(naked) static void itk1_visitor(void) {
    __asm {
        mov dword ptr [edi + 0xA300], ecx
        pushfd
        pushad
        lea eax, [edi + 0xA300]
        push eax
        call itk_rescheduled
        add esp, 4
        popad
        popfd
        push 0x423A75
        ret
    }
}

__declspec(naked) static void itk1_bought(void) {
    __asm {
        pushfd
        pushad
        push eax
        lea ecx, [edi + 0xA300]
        push ecx
        call itk_note
        add esp, 8
        popad
        popfd
        mov dword ptr [edi + 0xA300], eax
        push 0x456B4D
        ret
    }
}

static const itk_site ITK_VV1_SITES[] = {
    { 0x4237BDu, 12, { 0x39, 0x87, 0x00, 0xA3, 0x00, 0x00, 0x0F, 0x87, 0xF5, 0x02, 0x00, 0x00 }, (void *)itk1_trigger },
    { 0x423891u, 6, { 0x89, 0xAF, 0x00, 0xA3, 0x00, 0x00 }, (void *)itk1_crate },
    { 0x42391Au, 6, { 0x89, 0x8D, 0x00, 0xA3, 0x00, 0x00 }, (void *)itk1_island },
    { 0x423A37u, 10, { 0x81, 0x80, 0x00, 0xA3, 0x00, 0x00, 0x08, 0x07, 0x00, 0x00 }, (void *)itk1_first },
    { 0x423A6Fu, 6, { 0x89, 0x8F, 0x00, 0xA3, 0x00, 0x00 }, (void *)itk1_visitor },
    { 0x456B47u, 6, { 0x89, 0x87, 0x00, 0xA3, 0x00, 0x00 }, (void *)itk1_bought },
};
