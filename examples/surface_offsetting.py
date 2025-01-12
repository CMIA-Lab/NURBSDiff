import torch
import numpy as np
torch.manual_seed(120)
from tqdm import tqdm
from pytorch3d.loss import chamfer_distance
from NURBSDiff.surf_eval import SurfEval
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
import offset_eval as off
import sys
sys.path.insert(0, 'D:/Reasearch Data and Codes/ray_inter_nurbs')
import CPU_Eval as cpu

def main():
    timing = []
    eval_pts_size = 100
    eval_pts_size_HD = 100

    off_dist = 5
    cuda = False

    # Turbine Blade Surfaces
    # num_ctrl_pts1 = 50
    # num_ctrl_pts2 = 24
    # ctrl_pts = np.load('TurbineBladeCtrlPts.npy').astype('float32')
    # Element_Array = np.array([0, 1])
    # knot_u = np.load('TurbineKnotU.npy')
    # knot_v = np.load('TurbineKnotV.npy')

    # Cardiac Model Surfaces
    # num_ctrl_pts1 = 4
    # num_ctrl_pts2 = 4
    # ctrl_pts = np.load('CNTRL_PTS_2_Chamber.npy').astype('float32')
    # # ctrl_pts[:, :, :, -1] = 1.0
    # Element_Array = np.array([24, 30])
    # ctrl_pts = ctrl_pts[0, :, :, :3]
    # knot_u = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
    # knot_v = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])

    # Roof Files
    # num_ctrl_pts1 = 6
    # num_ctrl_pts2 = 6
    # ctrl_pts = np.load('CtrlPtsRoof.npy').astype('float32')
    # Element_Array = np.array([0])
    # ctrl_pts = ctrl_pts[:, :, :3]
    # knot_u = np.array([0.0, 0.0, 0.0, 0.0, 0.33, 0.67, 1.0, 1.0, 1.0, 1.0])
    # knot_v = np.array([0.0, 0.0, 0.0, 0.0, 0.33, 0.67, 1.0, 1.0, 1.0, 1.0])

    # Double Curve
    num_ctrl_pts1 = 6
    num_ctrl_pts2 = 6
    ctrl_pts = np.load('DoubleCurve.npy').astype('float32')
    Element_Array = np.array([0])
    ctrl_pts = np.reshape(ctrl_pts, [1, ctrl_pts.shape[0], 3])
    knot_u = np.array([0.0, 0.0, 0.0, 0.0, 0.33, 0.67, 1.0, 1.0, 1.0, 1.0])
    knot_v = np.array([0.0, 0.0, 0.0, 0.0, 0.33, 0.67, 1.0, 1.0, 1.0, 1.0])

    edge_pts_count = 2 * (num_ctrl_pts1 + num_ctrl_pts2 - 2)
    CtrlPtsNormal = np.empty([Element_Array.size, num_ctrl_pts1 * num_ctrl_pts2, 3])
    EdgePtsIdx = np.empty([Element_Array.size, edge_pts_count, 4], dtype=np.int)
    EdgeCtrlPtsMap = np.empty([Element_Array.size, ctrl_pts.shape[1], 3], dtype=np.uint)
    if Element_Array.size > 1:
        EdgeCtrlPtsMap = off.Map_Ctrl_Point(ctrl_pts[Element_Array, :, :3])

    for i in range(Element_Array.size):
        CtrlPtsNormal[i], EdgePtsIdx[i] = cpu.Compute_CNTRLPTS_Normals(ctrl_pts[Element_Array[i]], num_ctrl_pts1, num_ctrl_pts2, edge_pts_count, 4)

    EdgePtsIdx = cpu.Map_edge_points(ctrl_pts[Element_Array], EdgePtsIdx)

    CtrlPtsNormal = cpu.Normals_reassign(EdgePtsIdx, CtrlPtsNormal)

    temp_2 = cpu.compute_model_offset(ctrl_pts[Element_Array], CtrlPtsNormal, num_ctrl_pts1, num_ctrl_pts2, 3, knot_u, knot_v, off_layer=2, thickness=off_dist)
    weights = torch.ones(Element_Array.size, num_ctrl_pts1, num_ctrl_pts2, 1)
    CtrlPtsOffset = torch.cat((torch.from_numpy(np.reshape(temp_2[1],[Element_Array.size, num_ctrl_pts1, num_ctrl_pts2,3])), weights), axis=-1)

    off_pts = off.compute_surf_offset(ctrl_pts[Element_Array], knot_u, knot_v, 3, eval_pts_size, -off_dist)
    Max_size = off.Max_size(off_pts)
    target = torch.from_numpy(np.reshape(off_pts, [Element_Array.size, eval_pts_size, eval_pts_size, 3]))

    temp = np.reshape(ctrl_pts[Element_Array], [ctrl_pts[Element_Array].shape[0], num_ctrl_pts1, num_ctrl_pts2, 3])
    isolate_pts = torch.from_numpy(temp)
    weights = torch.ones(Element_Array.size, num_ctrl_pts1, num_ctrl_pts2, 1)
    base_inp_ctrl_pts = torch.cat((isolate_pts, weights), axis=-1)
    # inp_ctrl_pts = torch.nn.Parameter(isolate_pts)
    inp_ctrl_pts = torch.nn.Parameter(base_inp_ctrl_pts)

    layer = SurfEval(num_ctrl_pts1, num_ctrl_pts2, knot_u=knot_u, knot_v=knot_v, dimension=3, p=3, q=3, out_dim_u=eval_pts_size, out_dim_v=eval_pts_size)
    layer_2 = SurfEval(num_ctrl_pts1, num_ctrl_pts2, knot_u=knot_u, knot_v=knot_v, dimension=3, p=3, q=3, out_dim_u=eval_pts_size_HD, out_dim_v=eval_pts_size_HD)
    BaseSurf = layer_2(base_inp_ctrl_pts)

    CtrlPtsOffsetSurf = layer_2(CtrlPtsOffset)
    BaseSurf_pts = BaseSurf.detach().cpu().numpy().squeeze()
    CtrlPtsOffsetSurf_Pts = CtrlPtsOffsetSurf.detach().cpu().numpy().squeeze()
    # ctrl_pts_2 = np.reshape(ctrl_pts, [num_ctrl_pts1, num_ctrl_pts2, 3])

    opt = torch.optim.Adam(iter([inp_ctrl_pts]), lr=0.01)
    pbar = tqdm(range(20000))
    for i in pbar:
        opt.zero_grad()
        # weights = torch.ones(Element_Array.size, num_ctrl_pts1, num_ctrl_pts2, 1)
        # out = layer(torch.cat((inp_ctrl_pts, weights), axis=-1))
        out = layer(inp_ctrl_pts)
        loss = ((target-out)**2).mean()
        loss.backward()
        opt.step()

        if (i) % 100000 == 0:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d', adjustable='box', proj_type='ortho')

            target_mpl = np.reshape(target.cpu().numpy().squeeze(), [eval_pts_size * eval_pts_size, 3])
            predicted = out.detach().cpu().numpy().squeeze()
            predctrlpts = inp_ctrl_pts.detach().cpu().numpy().squeeze()
            predctrlpts = predctrlpts[:, :, :3] / predctrlpts[:, :, 3:]
            surf1 = ax.scatter(target_mpl[:, 0], target_mpl[:, 1], target_mpl[:, 2], s=1.0, color='red', label='Target Offset surface')
            # surf1 = ax.plot_wireframe(ctrlpts[:, :, 0], ctrlpts[:, :, 1], ctrlpts[:, :, 2], linestyle='dashed',
            #                           color='orange', label='Target CP')

            # surf2 = ax.plot_surface(predicted[:, :, 0], predicted[:, :, 1], predicted[:, :, 2], color='green', label='Predicted Surface')
            # surf2 = ax.plot_wireframe(predctrlpts[:, :, 0], predctrlpts[:, :, 1], predctrlpts[:, :, 2],
            #                           linestyle='dashed', color='orange', label='Predicted CP')

            surf3 = ax.plot_surface(BaseSurf_pts[:, :, 0], BaseSurf_pts[:, :, 1], BaseSurf_pts[:, :, 2], color='blue', alpha=1)
            # surf3 = ax.plot_wireframe(temp[0, :, :, 0], temp[0, :, :, 1], temp[0, :, :, 2], linestyle='dashed', color='pink', label='Predicted CP')

            # surf4 = ax.plot_surface(CtrlPtsOffsetSurf_Pts[:, :, 0], CtrlPtsOffsetSurf_Pts[:, :, 1], CtrlPtsOffsetSurf_Pts[:, :, 2], color='yellow')

            # ax.set_zlim(-1,3)
            # ax.set_xlim(-1,4)
            # ax.set_ylim(-2,2)

            ax.set_box_aspect([1.2, 1.2, 0.35])
            # ax.azim = 46
            # ax.dist = 10
            # ax.elev = 30
            # ax.set_xticks([])
            # ax.set_yticks([])
            # ax.set_zticks([])
            # ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
            # ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
            # ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
            # ax._axis3don = False
            # ax.legend()

            # ax.set_aspect(1)
            # fig.subplots_adjust(hspace=0, wspace=0)
            # fig.tight_layout()
            plt.show()

        if loss.item() < 5e-4:
            break
        pbar.set_description("Mse Loss is %s: %s" % (i+1, loss.item()))

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection='3d', adjustable='box')
    out = layer(inp_ctrl_pts)
    predicted = out.detach().cpu().numpy().squeeze()
    predctrlpts = inp_ctrl_pts.detach().cpu().numpy().squeeze()
    predctrlpts = predctrlpts[:, :, :3] / predctrlpts[:, :, 3:]
    surf2 = ax.plot_surface(predicted[:, :, 0], predicted[:, :, 1], predicted[:, :, 2], color='green',
                            label='Predicted Surface', alpha=0.6)
    surf2 = ax.plot_wireframe(predctrlpts[:, :, 0], predctrlpts[:, :, 1], predctrlpts[:, :, 2],
                              linestyle='dashed', color='orange', label='Predicted CP')
    surf3 = ax.plot_surface(BaseSurf_pts[:, :, 0], BaseSurf_pts[:, :, 1], BaseSurf_pts[:, :, 2], color='blue')

    # surf4 = ax.plot_surface(CtrlPtsOffsetSurf_Pts[:, :, 0], CtrlPtsOffsetSurf_Pts[:, :, 1],
    #                         CtrlPtsOffsetSurf_Pts[:, :, 2], color='yellow')

    ax.azim = 45
    ax.dist = 10
    ax.elev = 30
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])

    ax.set_box_aspect([1, 1, 0.5])
    ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax._axis3don = False
    # ax.legend(loc='upper left')

    # ax.set_aspect(1)
    fig.subplots_adjust(hspace=0, wspace=0)
    fig.tight_layout()
    plt.show()

    # layer_2 = SurfEval(num_ctrl_pts1, num_ctrl_pts2, knot_u=knot_u, knot_v=knot_v, dimension=3, p=3, q=3,
    #                    out_dim_u=100, out_dim_v=100)
    weights = torch.ones(Element_Array.size, num_ctrl_pts1, num_ctrl_pts2, 1)
    out = layer_2(torch.cat((inp_ctrl_pts, weights), axis=-1))
    out_2 = out.view(1, eval_pts_size_HD * eval_pts_size_HD, 3)
    target_2 = target.view(1, eval_pts_size * eval_pts_size, 3)

    print('Offset Distance is  ==  ', off_dist)

    print('Max Size is  ==  ', Max_size)

    loss_CP_PC, _ = chamfer_distance(CtrlPtsOffsetSurf.view(Element_Array.size, eval_pts_size_HD * eval_pts_size_HD, 3), target_2)
    print('Chamfer loss  --  Control Point , Point Cloud   ==  ', loss_CP_PC * 10000)

    loss_Pred_PC, _ = chamfer_distance(target_2, out_2)
    print('Chamfer loss  --  Predicted, Point Cloud   ==  ', loss_Pred_PC * 10000)

    loss_CP_Base, _ = chamfer_distance(CtrlPtsOffsetSurf.view(Element_Array.size, eval_pts_size_HD * eval_pts_size_HD, 3), BaseSurf.view(Element_Array.size, eval_pts_size_HD * eval_pts_size_HD, 3))
    print('Chamfer loss  --  Control Point, Base   ==  ', loss_CP_Base * 10000)

    loss_Pred_Base, _ = chamfer_distance(BaseSurf.view(Element_Array.size, eval_pts_size_HD * eval_pts_size_HD, 3), out_2)
    print('Chamfer loss  --  Predicted , Base   ==  ', loss_Pred_Base * 10000)

    loss_CP_Pred, _ = chamfer_distance(CtrlPtsOffsetSurf.view(Element_Array.size, eval_pts_size_HD * eval_pts_size_HD, 3), out_2)
    print('Chamfer loss  --  Control Point , Predicted   ==  ', loss_CP_Pred * 10000)


if __name__ == '__main__':
    main()
