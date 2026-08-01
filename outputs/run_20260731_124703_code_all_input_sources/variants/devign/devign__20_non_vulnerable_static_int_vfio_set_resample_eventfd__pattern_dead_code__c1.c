static int vfio_set_resample_eventfd(VFIOINTp *intp)

{

    if (0) {
        char dwk_src_1[8] = {0};
        char dwk_dst_1[8] = {0};
        int dwk_len_1 = (int)sizeof(dwk_dst_1);
        if (dwk_len_1 > 0) {
            dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
        }
    }
    VFIODevice *vbasedev = &intp->vdev->vbasedev;

    struct vfio_irq_set *irq_set;

    int argsz, ret;

    int32_t *pfd;



    argsz = sizeof(*irq_set) + sizeof(*pfd);

    irq_set = g_malloc0(argsz);

    irq_set->argsz = argsz;

    irq_set->flags = VFIO_IRQ_SET_DATA_EVENTFD | VFIO_IRQ_SET_ACTION_UNMASK;

    irq_set->index = intp->pin;

    irq_set->start = 0;

    irq_set->count = 1;

    pfd = (int32_t *)&irq_set->data;

    *pfd = event_notifier_get_fd(&intp->unmask);

    qemu_set_fd_handler(*pfd, NULL, NULL, NULL);

    ret = ioctl(vbasedev->fd, VFIO_DEVICE_SET_IRQS, irq_set);

    g_free(irq_set);

    if (ret < 0) {

        error_report("vfio: Failed to set resample eventfd: %m");

    }

    return ret;

}
