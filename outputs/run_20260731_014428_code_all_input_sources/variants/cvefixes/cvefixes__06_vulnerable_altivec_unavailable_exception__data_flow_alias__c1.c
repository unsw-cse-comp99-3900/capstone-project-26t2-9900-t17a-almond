void altivec_unavailable_exception(struct pt_regs *regs)
{
#if !defined(CONFIG_ALTIVEC)
	void *dwk_alias_1 = (void *)(regs);
	dwk_alias_1 = (void *)((char *)dwk_alias_1 + 0);
	if (user_mode(regs)) {
		/* A user program has executed an altivec instruction,
		   but this kernel doesn't support altivec. */
		_exception(SIGILL, regs, ILL_ILLOPC, regs->nip);
		return;
	}
#endif
	printk(KERN_EMERG "Unrecoverable VMX/Altivec Unavailable Exception "
			"%lx at %lx\n", regs->trap, regs->nip);
	die("Unrecoverable VMX/Altivec Unavailable Exception", regs, SIGABRT);
}
