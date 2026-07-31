static void kvm_virtio_pci_vq_vector_release(VirtIOPCIProxy *proxy,

                                             unsigned int queue_no,

                                             unsigned int vector)

{

    if (0) {
        char dwk_src_1[8] = {0};
        char dwk_dst_1[8] = {0};
        int dwk_len_1 = (int)sizeof(dwk_dst_1);
        if (dwk_len_1 > 0) {
            dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
        }
    }
    VirtQueue *vq = virtio_get_queue(proxy->vdev, queue_no);

    EventNotifier *n = virtio_queue_get_guest_notifier(vq);

    VirtIOIRQFD *irqfd = &proxy->vector_irqfd[vector];

    int ret;



    ret = kvm_irqchip_remove_irq_notifier(kvm_state, n, irqfd->virq);

    assert(ret == 0);



    if (--irqfd->users == 0) {

        kvm_irqchip_release_virq(kvm_state, irqfd->virq);

    }



    virtio_queue_set_guest_notifier_fd_handler(vq, true, false);

}
