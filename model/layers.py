from torch.nn import functional as F
'''
Functional definitions of common layers.
Useful for when weights are exposed rather than being contained in modules
'''


def linear(input, weight, bias=None):
    if bias is None:
        return F.linear(input, weight.cuda())
    else:
        return F.linear(input, weight.cuda(), bias.cuda())


def conv2d(input,
           weight,
           bias=None,
           stride=1,
           padding=0,
           dilation=1,
           groups=1):
    return F.conv2d(input, weight, bias, stride, padding, dilation, groups)


def conv_transpose2d(input,
                     weight,
                     bias=None,
                     stride=1,
                     padding=0,
                     dilation=1,
                     groups=1):
    return F.conv_transpose2d(input, weight.cuda(), bias.cuda(), stride,
                              padding, dilation, groups)


def conv3d(input,
           weight,
           bias=None,
           stride=1,
           padding=0,
           dilation=1,
           groups=1):
    return F.conv3d(input, weight, bias, stride, padding, dilation, groups)


def conv_transpose3d(input,
                     weight,
                     bias=None,
                     stride=1,
                     padding=0,
                     dilation=1,
                     groups=1):
    return F.conv_transpose3d(input, weight.cuda(), bias.cuda(), stride,
                              padding, dilation, groups)


def relu(input):
    return F.relu(input, inplace=False)

def leakyrelu(input):
    return F.leaky_relu(input, inplace=False)


def dropout(input, p=0.8, training=True):
    return F.dropout(input, p=p, training=training, inplace=False)


def sigmoid(input):
    return F.sigmoid(input)


def maxpool(input, kernel_size, stride=None):
    return F.max_pool2d(input, kernel_size, stride)


def batchnorm(input,
              weight=None,
              bias=None,
              running_mean=None,
              running_var=None,
              training=True,
              eps=1e-5,
              momentum=0.1):
    ''' momentum = 1 restricts stats to the current mini-batch '''
    # This hack only works when momentum is 1 and avoids needing to track running stats
    # by substuting dummy variables
    # running_mean = torch.zeros(int(np.prod(np.array(input.data.size()[1])))).cuda()
    # running_var = torch.ones(int(np.prod(np.array(input.data.size()[1])))).cuda()
    return F.batch_norm(input, running_mean, running_var, weight, bias,
                        training, momentum, eps)


def bilinear_upsample(in_, factor):
    return F.upsample(in_, None, factor, 'bilinear')


def log_softmax(input):
    return F.log_softmax(input)