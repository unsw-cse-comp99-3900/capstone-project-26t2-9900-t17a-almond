static void emulate_spapr_hypercall(CPUPPCState *env)

{

    env->gpr[3] = spapr_hypercall(env, env->gpr[3], &env->gpr[4]);

}
