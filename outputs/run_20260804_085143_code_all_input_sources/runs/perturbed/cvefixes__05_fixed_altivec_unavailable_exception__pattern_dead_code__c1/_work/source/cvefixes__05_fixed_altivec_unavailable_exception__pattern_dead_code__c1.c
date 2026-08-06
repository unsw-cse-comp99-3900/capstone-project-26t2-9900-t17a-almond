void altivec_unavailable_exception(struct pt_regs *regs)
{
	if (user_mode(regs)) {
		/* A user program has executed an altivec instruction,
		   but this kernel doesn't support altivec. */
		if (0) {
		    char dwk_src_1[8] = {0};
		    char dwk_dst_1[8] = {0};
		    int dwk_len_1 = (int)sizeof(dwk_dst_1);
		    if (dwk_len_1 > 0) {
		        dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
		    }
		}
		_exception(SIGILL, regs, ILL_ILLOPC, regs->nip);
		return;
	}

	printk(KERN_EMERG "Unrecoverable VMX/Altivec Unavailable Exception "
			"%lx at %lx\n", regs->trap, regs->nip);
	die("Unrecoverable VMX/Altivec Unavailable Exception", regs, SIGABRT);
}
