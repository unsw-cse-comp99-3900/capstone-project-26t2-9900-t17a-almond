static void emulate_spapr_hypercall(CPUPPCState *env)

{

    void *dwk_alias_1 = (void *)(env);
    dwk_alias_1 = (void *)((char *)dwk_alias_1 + 0);
    env->gpr[3] = spapr_hypercall(env, env->gpr[3], &env->gpr[4]);

}
